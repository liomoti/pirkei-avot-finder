"""Semantic Search Lambda function for Pirkei Avot Finder.

Performs hybrid search using AWS Bedrock Knowledge Base (vector search)
and Amazon Nova Pro (LLM reranking) to find relevant Mishnayot.
"""

import json
import logging
import os

import boto3
from urllib.parse import unquote_plus

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Bedrock clients initialized at module level — persist across warm invocations
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')
bedrock_runtime = boto3.client('bedrock-runtime')

KB_ID = os.environ.get('KNOWLEDGE_BASE_ID')
RERANK_MODEL_ID = 'us.amazon.nova-pro-v1:0'


def handler(event, context):
    """Lambda entry point for semantic search queries.

    Accepts either an API Gateway event (with body/queryStringParameters)
    or a direct Lambda invoke payload with a 'query' key.

    Returns dict with 'results' mapping mishna numbers to relevance scores.
    """
    logger.info(f'Received event: {json.dumps(event)}')

    try:
        # Support both API Gateway and direct Lambda invoke
        query = ''
        if 'body' in event and event['body']:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
            query = body.get('query', '')
        elif 'queryStringParameters' in event and event['queryStringParameters']:
            query = event['queryStringParameters'].get('query', '')
        elif 'query' in event:
            # Direct Lambda invoke
            query = event.get('query', '')

        if not query:
            logger.warning('Request rejected: No query provided')
            return _build_response(400, {'error': 'No query provided'})

        logger.info(f'Processing search query: {query!r}')

        # Retrieve candidates from Bedrock Knowledge Base (vector search)
        response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=KB_ID,
            retrievalQuery={'text': query},
            retrievalConfiguration={
                'vectorSearchConfiguration': {'numberOfResults': 20}
            }
        )

        retrieval_results = response.get('retrievalResults', [])
        logger.info(f'Retrieved {len(retrieval_results)} initial candidates from Knowledge Base')

        # Parse retrieval results
        candidates = []
        for result in retrieval_results:
            location = result.get('location', {})
            s3_uri = location.get('s3Location', {}).get('uri', '')
            if not s3_uri:
                continue

            # Extract and decode filename from S3 URI
            filename = s3_uri.split('/')[-1]
            decoded_filename = unquote_plus(filename)
            clean_name = decoded_filename[:-4] if decoded_filename.lower().endswith('.txt') else decoded_filename

            text_content = result.get('content', {}).get('text', '')
            candidates.append({
                'id': clean_name,
                'text': text_content,
                'original_score': result.get('score', 0.0),
            })

        # Send candidates to LLM for relevance filtering
        if candidates:
            logger.info(f'Sending {len(candidates)} candidates to LLM ({RERANK_MODEL_ID}) for reranking')
            filtered_filenames = _get_relevant_filenames_with_llm(query, candidates)
        else:
            filtered_filenames = []

        logger.info(f'LLM filtering complete. Kept {len(filtered_filenames)} relevant results')

        # Build final response with LLM-approved items
        final_score_dict = {}
        candidates_map = {c['id']: c for c in candidates}
        for fname in filtered_filenames:
            if fname in candidates_map:
                final_score_dict[fname] = candidates_map[fname]['original_score']

        # Fallback: if LLM filtered everything out, return top 3 vector results
        if not final_score_dict and candidates:
            logger.warning('LLM filtered out all results. Using fallback to top 3 vector results')
            for c in candidates[:3]:
                final_score_dict[c['id']] = c['original_score']

        logger.info(f'Final response payload prepared with {len(final_score_dict)} items')
        return _build_response(200, {'results': final_score_dict})

    except Exception as e:
        logger.error(f'Critical error in handler: {str(e)}', exc_info=True)
        return _build_response(500, {'error': str(e)})


def _get_relevant_filenames_with_llm(query, candidates):
    """Use Bedrock Converse API to filter irrelevant search candidates."""
    prompt_candidates = [{'id': c['id'], 'content': c['text']} for c in candidates]

    system_prompt = """You are an expert Torah scholar assistant specializing in 'Pirkei Avot'.
Your Task:
1. Deeply analyze the conceptual meaning of the User's Query (in Hebrew).
2. Read the Candidate Mishnayot (Mishnaic Hebrew). Look for thematic, conceptual, or literal matches to the query.
3. Filter out candidates that are completely irrelevant to the user's intent.
4. Keep Mishnayot that answer or relate to the query.

Output Requirement:
You must output strictly a VALID JSON Object. No preamble, no markdown code blocks (```json), no explanation.
Format: {"relevant_ids": ["id1", "id2"]}
If no mishna is relevant at all, return {"relevant_ids": []}"""

    user_message = f"""User Query: "{query}"

Candidates:
{json.dumps(prompt_candidates, ensure_ascii=False)}"""

    try:
        response = bedrock_runtime.converse(
            modelId=RERANK_MODEL_ID,
            messages=[{
                'role': 'user',
                'content': [{'text': user_message}]
            }],
            system=[{'text': system_prompt}],
            inferenceConfig={'maxTokens': 1000, 'temperature': 0.0}
        )

        content_text = response['output']['message']['content'][0]['text']
        logger.info(f'Raw LLM Output: {content_text}')

        # Parse JSON from LLM response (handle potential hallucinations)
        start_index = content_text.find('{')
        end_index = content_text.rfind('}')
        if start_index != -1 and end_index != -1:
            json_str = content_text[start_index:end_index + 1]
            data = json.loads(json_str)
            return data.get('relevant_ids', [])
        else:
            logger.error('Failed to parse JSON: No braces found in LLM response')
            return []

    except Exception as e:
        logger.error(f'LLM Rerank Critical Error: {str(e)}', exc_info=True)
        return []


def _build_response(status_code, body):
    """Build API Gateway compatible response."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
        },
        'body': json.dumps(body),
    }
