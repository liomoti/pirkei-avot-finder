# Semantic AI Search Implementation

## Overview
The Semantic AI Search feature uses sentence transformers to find mishnas based on semantic meaning rather than exact text matches.

## Components Added

### 1. Dependencies (requirements.txt)
- `sentence-transformers==3.3.1` - For encoding text into vectors (updated for compatibility)
- `pgvector==0.2.4` - PostgreSQL extension for vector similarity search

### 2. Model (models.py)
- Added `Vector` import from pgvector
- The `Mishna` model already has an `embedding` column of type `Vector(768)`

### 3. Routes (routes.py)
- Imported `SentenceTransformer` and initialized the Hebrew model: `imvladikon/sentence-transformers-alephbert`
- Added `search_semantic` action handler that:
  - Encodes the user's query into a 768-dimensional vector
  - Performs vector similarity search using PostgreSQL's `<=>` operator
  - Filters results by distance threshold (< 0.7)
  - Returns the most semantically similar mishnas

### 4. Frontend (templates/index.html)
- Already has the AI search UI with sparkle animations
- Form field `semantic_query` captures user input
- Search button triggers the `search_semantic` action

## How It Works

1. User enters a natural language query (e.g., "משניות על כבוד האדם")
2. The query is encoded into a vector using the AlephBERT model
3. PostgreSQL compares this vector with stored mishna embeddings
4. Results are ranked by semantic similarity (distance)
5. Only mishnas with distance < 0.7 are returned

## Installation

```bash
pip install -r requirements.txt
```

## Database Requirements

- PostgreSQL with pgvector extension enabled
- Mishna table must have embeddings populated in the `embedding` column
- Embeddings should be 768-dimensional vectors from the same AlephBERT model

## Configuration

You can adjust the similarity threshold in routes.py:
```python
if distance < 0.7:  # Lower = more strict, Higher = more lenient
```

## Performance Notes

- The model is loaded once at startup (global variable)
- First query may be slower as the model initializes
- Vector similarity search is optimized by PostgreSQL's pgvector extension
