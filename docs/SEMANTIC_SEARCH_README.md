# Semantic Search Module

## Overview
The `semantic_search.py` module provides intelligent semantic similarity search for Mishna texts using vector embeddings and the AlephBERT Hebrew language model.

## How It Works

### 1. Query Encoding
- Converts your search query into a 768-dimensional vector using the AlephBERT model
- This captures the semantic meaning of the text, not just keywords

### 2. Vector Similarity Search
- Uses PostgreSQL's pgvector extension with cosine distance (`<=>` operator)
- Retrieves top 50 candidates from the database
- Cosine distance ranges from 0 (identical) to 2 (opposite)

### 3. Adaptive Threshold Calculation
The system intelligently determines which results are relevant based on:

#### Quality-Based Thresholds
- **Excellent match** (distance < 0.55): Strict filtering, max threshold 0.62
- **Good match** (0.55-0.60): Moderate filtering, max threshold 0.65
- **Decent match** (0.60-0.65): Lenient filtering, max threshold 0.68
- **Poor match** (> 0.65): Most lenient, max threshold 0.72

#### Gap Analysis
- Analyzes the first 15 results for significant gaps in distance
- A "gap" is a jump between consecutive distances
- If a significant gap is found, it's used as a natural cutoff point
- This helps separate relevant results from noise

#### Fallback Strategy
- If no clear gap exists, returns top 5-7 results based on quality
- Better matches → fewer results (top 5)
- Worse matches → more results (top 7)

### 4. Result Filtering
- Accepts all results below the calculated threshold
- Handles borderline cases: if fewer than 3 results, considers items within 0.05 of threshold
- Attaches `similarity_score` attribute to each Mishna object

## Usage

```python
from utils.semantic_search import SemanticSearchEngine
from sentence_transformers import SentenceTransformer

# Initialize
model = SentenceTransformer('imvladikon/sentence-transformers-alephbert')
search_engine = SemanticSearchEngine(model)

# Search
results = search_engine.search("מהו דין שבת?")

# Access results
for mishna in results:
    print(f"Mishna {mishna.id}: {mishna.text_raw}")
    print(f"Similarity score: {mishna.similarity_score:.4f}")
```

## Key Classes and Methods

### `SemanticSearchEngine`
Main class that orchestrates the search process.

#### Methods:
- `search(query_text, max_candidates=50)` - Main entry point for searching
- `_encode_query(query_text)` - Converts text to vector
- `_retrieve_candidates(query_vector, max_candidates)` - Gets candidates from DB
- `_calculate_threshold(all_distances)` - Determines cutoff distance
- `_filter_results(candidates, cutoff_distance)` - Filters and returns final results

## Distance Interpretation

| Distance Range | Meaning |
|---------------|---------|
| 0.00 - 0.55 | Excellent semantic match |
| 0.55 - 0.60 | Good semantic match |
| 0.60 - 0.65 | Decent semantic match |
| 0.65 - 0.72 | Weak semantic match |
| > 0.72 | Poor match (usually filtered out) |

## Logging
The module logs detailed information at each step:
- Query encoding
- Candidate retrieval with distance ranges
- Threshold calculation decisions
- Accepted, borderline, and rejected results

Check your application logs for debugging information.

## Dependencies
- `sentence-transformers` - For text encoding
- `sqlalchemy` - For database queries
- `flask` - For logging via current_app
- PostgreSQL with `pgvector` extension

## Database Requirements
Your `mishna` table must have:
- `embedding` column of type `vector` (created by pgvector extension)
- Pre-computed embeddings for all texts
- Index on embedding column for fast similarity search

## Performance Considerations
- Model is loaded once at application startup (global variable)
- Vector search is optimized with pgvector indexes
- Retrieves only top 50 candidates to balance accuracy and speed
- Adaptive thresholds prevent returning too many irrelevant results
