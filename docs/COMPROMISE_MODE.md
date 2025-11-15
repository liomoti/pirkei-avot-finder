# Compromise Mode Feature

## Overview

Compromise Mode is an intelligent fallback mechanism for semantic search that ensures users always get relevant results, even when no matches meet the strict initial similarity threshold.

## How It Works

### Normal Search Flow
1. User performs a semantic search with query text
2. System searches for results with similarity ≥ 70% (MIN_SIMILARITY_SCORE)
3. If results are found → return them to the user

### Compromise Mode Flow
1. If NO results are found at 70% threshold
2. **Compromise Mode activates automatically**
3. Reduce threshold by 5% → search again at 65%
4. Still no results? → Reduce by 5% again → search at 60%
5. Continue until:
   - Results are found, OR
   - Threshold reaches minimum of 30%

### Result Limiting
- **Normal mode**: Returns all results above threshold
- **Compromise mode**: Returns maximum of 3 results
  - This prevents overwhelming users with lower-quality matches

## Configuration

All configuration is in `utils/compromise_mode.py`:

```python
REDUCTION_STEP = 5          # Reduce threshold by 5% each iteration
MIN_THRESHOLD = 30          # Never go below 30% similarity
MAX_RESULTS_IN_COMPROMISE = 3  # Limit results in compromise mode
```

## Example Scenarios

### Scenario 1: Results Found at 65%
```
Initial search at 70% → No results
Compromise: Try 65% → Found 5 results
Return: Top 3 results (compromise mode limit)
```

### Scenario 2: Results Found at 45%
```
Initial search at 70% → No results
Compromise: Try 65% → No results
Compromise: Try 60% → No results
Compromise: Try 55% → No results
Compromise: Try 50% → No results
Compromise: Try 45% → Found 2 results
Return: 2 results (under limit)
```

### Scenario 3: No Results Even at 30%
```
Initial search at 70% → No results
Compromise: Try 65%, 60%, 55%, 50%, 45%, 40%, 35%, 30% → No results
Return: Empty list (no matches found)
```

## Code Structure

### Main Components

1. **`CompromiseMode` class** (`utils/compromise_mode.py`)
   - Manages threshold reduction logic
   - Tracks compromise mode state
   - Limits results when active

2. **`search_with_compromise()` function** (`utils/compromise_mode.py`)
   - Wrapper function that handles the retry loop
   - Calls the search function with progressively lower thresholds
   - Returns results + compromise status info

3. **`SemanticSearchEngine.search_with_compromise()` method** (`utils/semantic_search.py`)
   - Integration point in the semantic search engine
   - Uses the compromise mode wrapper

4. **Routes integration** (`routes.py`)
   - Semantic search route now uses `search_with_compromise()`
   - Logs compromise mode activation for monitoring

## Usage

### In Application Code

```python
# Use compromise mode (recommended for user-facing searches)
results, compromise_info = semantic_search_engine.search_with_compromise(query_text)

# Check if compromise mode was activated
if compromise_info['is_active']:
    print(f"Found results at {compromise_info['current_threshold']}%")
    print(f"Made {compromise_info['attempts']} attempts")
```

### Direct Search (No Compromise)

```python
# Use direct search with fixed threshold (for specific use cases)
results = semantic_search_engine.search(query_text, min_similarity_score=70)
```

## Testing

Run the test script to verify compromise mode behavior:

```bash
cd utils
python test_compromise_mode.py
```

## Logging

Compromise mode logs detailed information:

```
INFO: Starting search with initial threshold: 70%
INFO: No results found at 70%, entering compromise mode
INFO: Compromise mode: Reducing threshold to 65% (attempt 1)
INFO: Compromise mode: Reducing threshold to 60% (attempt 2)
INFO: Compromise mode SUCCESS: Found 5 results at 60%
INFO: Compromise mode: Limiting results from 5 to 3
```

## Benefits

1. **Better User Experience**: Users always get results when possible
2. **Transparent**: Logs show when compromise mode activates
3. **Controlled**: Results are limited to prevent low-quality matches
4. **Maintainable**: Separate file makes it easy to adjust behavior
5. **Flexible**: Can be enabled/disabled per search if needed

## Future Enhancements

Possible improvements:
- Make reduction step configurable per search
- Add UI indicator when compromise mode was used
- Track compromise mode usage statistics
- Allow users to opt-in/opt-out of compromise mode
