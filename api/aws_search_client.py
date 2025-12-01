"""
AWS Semantic Search API Client

This module provides a client for interacting with the AWS API Gateway
semantic search service. It handles authentication, request formatting,
response parsing, and transformation of API results into application
domain objects.
"""

import os
import logging
from typing import List, Dict, Tuple, Optional
import requests
from flask import current_app
from models import Mishna


class AWSSearchError(Exception):
    """Exception raised for AWS API search errors."""
    pass


class AWSSemanticSearchClient:
    """
    Client for interacting with AWS API Gateway semantic search service.
    
    Handles authentication, request formatting, response parsing, and
    transformation of API results into application domain objects.
    """
    
    def __init__(self, api_key: str, api_url: str):
        """
        Initialize the AWS search client.
        
        Args:
            api_key: API key for authentication (from AWS_SEARCH_AI_KEY env var)
            api_url: Full URL of the AWS API Gateway endpoint
            
        Raises:
            ValueError: If api_key or api_url is empty
        """
        if not api_key or not api_key.strip():
            raise ValueError("API key cannot be empty")
        
        if not api_url or not api_url.strip():
            raise ValueError("API URL cannot be empty")
        
        self.api_key = api_key.strip()
        self.api_url = api_url.strip()
        self.timeout = 10  # seconds
        
        current_app.logger.info("AWS Semantic Search Client initialized")
    
    def search(self, query: str, min_score: float = 0.0) -> List[Mishna]:
        """
        Perform semantic search via AWS API.
        
        Args:
            query: Search query text
            min_score: Minimum relevance score threshold (default: 0.0)
            
        Returns:
            List of Mishna objects with similarity_score attribute attached,
            ordered by relevance score (highest first)
            
        Raises:
            AWSSearchError: If API request fails
        """
        current_app.logger.info(f"Starting AWS semantic search, query length: {len(query)}")
        
        try:
            # Make API request
            api_response = self._make_api_request(query)
            
            # Fetch Mishnas from database
            mishnas_with_scores = self._fetch_mishnas_from_db(api_response)
            
            # Filter by minimum score
            filtered_mishnas = [
                (mishna, score) for mishna, score in mishnas_with_scores
                if score >= min_score
            ]
            
            # Attach scores and sort by relevance
            results = []
            for mishna, score in filtered_mishnas:
                mishna.similarity_score = score
                results.append(mishna)
            
            # Sort by score descending
            results.sort(key=lambda m: m.similarity_score, reverse=True)
            
            # Log individual results with mishna identifier and relevance score
            current_app.logger.info(f"AWS semantic search completed, {len(results)} results returned")
            for mishna in results:
                mishna_id = f"{mishna.chapter}_{mishna.mishna}"
                current_app.logger.info(f"Result: Mishna {mishna_id} (number={mishna.number}) - Relevance: {mishna.similarity_score:.1f}%")
            
            # Log search summary
            current_app.logger.info(f"Search summary - Query: '{query[:100]}{'...' if len(query) > 100 else ''}' - Total results: {len(results)}")
            
            return results
            
        except AWSSearchError:
            raise
        except Exception as e:
            current_app.logger.error(f"Unexpected error in AWS semantic search: {str(e)}")
            raise AWSSearchError(f"Search failed: {str(e)}")
    
    def _make_api_request(self, query: str) -> dict:
        """
        Make HTTP POST request to AWS API Gateway.
        
        Args:
            query: Search query text
            
        Returns:
            Dictionary with 'results' key containing mishna_number -> score mapping
            
        Raises:
            AWSSearchError: If request fails or response is invalid
        """
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': self.api_key
        }
        
        # Prepare payload - Lambda expects query directly in JSON body
        payload = {
            'query': query
        }
        
        try:
            current_app.logger.info(f"Sending request to AWS API Gateway with query: {query[:50] if len(query) > 50 else query}...")
            current_app.logger.info(f"Payload: {payload}")
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            
            current_app.logger.info(f"AWS API responded with status code: {response.status_code}")
            current_app.logger.info(f"Response text: {response.text[:200] if len(response.text) > 200 else response.text}")
            
            # Check for HTTP errors
            if response.status_code != 200:
                error_msg = f"API returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                current_app.logger.warning(error_msg)
                raise AWSSearchError(error_msg)
            
            # Parse JSON response
            try:
                result = response.json()
                current_app.logger.info(f"API returned {len(result.get('results', {}))} results")
                return result
            except ValueError as e:
                current_app.logger.error(f"Failed to parse API response as JSON: {str(e)}")
                raise AWSSearchError("Invalid JSON response from API")
                
        except requests.exceptions.Timeout:
            current_app.logger.error("AWS API request timed out")
            raise AWSSearchError("API request timed out")
        except requests.exceptions.ConnectionError as e:
            current_app.logger.error(f"Network error calling AWS API: {str(e)}")
            raise AWSSearchError("Network connectivity error")
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Request error calling AWS API: {str(e)}")
            raise AWSSearchError(f"Request failed: {str(e)}")
    
    def _fetch_mishnas_from_db(self, results: dict) -> List[Tuple[Mishna, float]]:
        """
        Fetch Mishna records from database based on API results.
        
        Args:
            results: Dictionary with 'results' key mapping mishna numbers (as strings) to scores
            
        Returns:
            List of (Mishna, score) tuples for mishnas found in database
        """
        api_results = results.get('results', {})
        
        if not api_results:
            current_app.logger.info("No results returned from API")
            return []
        
        mishnas_with_scores = []
        
        for mishna_num_str, score in api_results.items():
            try:
                # Parse mishna number as integer
                mishna_num = int(mishna_num_str)
                
                # Query database for this Mishna
                mishna = Mishna.query.filter_by(number=mishna_num).first()
                
                if mishna:
                    mishnas_with_scores.append((mishna, float(score)))
                else:
                    current_app.logger.info(f"Mishna {mishna_num} not found in database, skipping")
                    
            except ValueError as e:
                current_app.logger.warning(f"Invalid mishna number format '{mishna_num_str}': {str(e)}")
                continue
        
        current_app.logger.info(f"Successfully retrieved {len(mishnas_with_scores)} Mishnas from database")
        
        return mishnas_with_scores
