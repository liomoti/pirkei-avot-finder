# Tag-Based Boosting for Semantic Search

## Overview
Enhanced the semantic search functionality to incorporate tag similarity into the scoring algorithm. This improves search results by boosting mishnas that have tags semantically similar to the user's query.

## How It Works

### 1. Tag Similarity Detection
When a user performs a semantic search:
- The query is encoded into a vector using the AlephBERT model
- All tags in the database are also encoded into vectors
- The system finds 1-3 tags most similar to the query (with distance < 0.7)

### 2. Score Boosting
For each mishna in the search results:
- If the mishna has tags that match the similar tags found
- Its similarity score is improved (distance is reduced)
- The boost amount is: `number_of_matching_tags × 0.15`

### 3. Example
**Query:** "כבוד אב ואם" (honoring parents)

**Process:**
1. System finds similar tags: ["משפחה", "מצוות", "כבוד"]
2. Mishna A has tags: ["משפחה", "כבוד"] → gets boost of 0.30 (2 × 0.15)
3. Mishna B has tags: ["משפחה"] → gets boost of 0.15 (1 × 0.15)
4. Mishna C has no matching tags → no boost

**Result:** Mishnas with relevant tags rank higher in search results

## Configuration

### Adjustable Parameters

In `utils/semantic_search.py`, you can modify:

```python
self.tag_boost_weight = 0.15  # Boost per matching tag
```

In `_find_similar_tags()` method:
```python
max_tags: int = 3  # Maximum similar tags to find
distance < 0.7     # Threshold for tag similarity
```

### Tuning Recommendations

- **Increase `tag_boost_weight`** (e.g., 0.20): Stronger preference for tag matches
- **Decrease `tag_boost_weight`** (e.g., 0.10): More balanced between text and tags
- **Increase `max_tags`** (e.g., 5): Consider more tags (may dilute relevance)
- **Decrease tag distance threshold** (e.g., 0.6): Only very similar tags count

## Technical Details

### New Methods Added

1. **`_find_similar_tags(query_vector, max_tags=3)`**
   - Encodes all tags in the database
   - Calculates cosine distance between query and each tag
   - Returns top 1-3 most similar tag IDs

2. **`_apply_tag_boost(candidates, similar_tag_ids)`**
   - Checks each mishna for matching tags
   - Reduces distance score for mishnas with matching tags
   - Re-sorts results by boosted scores

### Search Flow

```
User Query
    ↓
1. Encode query → vector
    ↓
2. Find similar tags (1-3)
    ↓
3. Retrieve candidates from DB (vector search)
    ↓
4. Apply tag boost to matching mishnas
    ↓
5. Calculate adaptive threshold
    ↓
6. Filter and return results
```

## Benefits

1. **Better Relevance**: Mishnas with topically relevant tags rank higher
2. **Semantic Understanding**: Tags provide additional semantic context
3. **Flexible**: Easy to tune the boost strength
4. **Transparent**: All boosting is logged for debugging

## Logging

The feature logs detailed information:
- Similar tags found: `Found 2 similar tags: [('משפחה', 0.45), ('כבוד', 0.52)]`
- Boost applied: `Mishna 1_5: original distance=0.62, boosted distance=0.47 (matched 2 tags)`

Check `logs/pirkey_avot.log` for detailed search behavior.

## Dependencies

No new dependencies required. Uses existing:
- `sentence-transformers` (includes numpy)
- `pgvector` for vector operations
- AlephBERT model for Hebrew text encoding
