"""
Compromise Mode Module

This module handles the progressive reduction of similarity thresholds when
no results are found above the initial MIN_SIMILARITY_SCORE.

The compromise mode works as follows:
1. If no results are found at the initial threshold (e.g., 70%)
2. Reduce the threshold by 5% and search again
3. Repeat until results are found OR threshold reaches 30%
4. In compromise mode, limit results to maximum 3 items

This ensures users always get some results when possible, even if they
don't meet the strict initial similarity requirements.
"""

from typing import List, Optional
from flask import current_app


class CompromiseMode:
    """
    Handles progressive threshold reduction for semantic search.
    
    When the initial search returns no results, this class manages
    the step-by-step reduction of the similarity threshold to find
    acceptable matches.
    """
    
    # Configuration constants
    REDUCTION_STEP = 5  # Reduce threshold by 5% each iteration
    MIN_THRESHOLD = 30  # Never go below 30% similarity
    MAX_RESULTS_IN_COMPROMISE = 3  # Limit results in compromise mode
    
    def __init__(self, initial_threshold: float):
        """
        Initialize compromise mode with the initial threshold.
        
        Args:
            initial_threshold: The starting similarity threshold (0-100%)
        """
        self.initial_threshold = initial_threshold
        self.current_threshold = initial_threshold
        self.is_active = False
        self.attempts = 0
    
    def should_continue(self) -> bool:
        """
        Check if compromise mode should continue trying lower thresholds.
        
        Returns:
            True if we can reduce the threshold further, False otherwise
        """
        return self.current_threshold > self.MIN_THRESHOLD
    
    def reduce_threshold(self) -> float:
        """
        Reduce the current threshold by the configured step amount.
        
        Returns:
            The new reduced threshold value
        """
        self.current_threshold = max(
            self.MIN_THRESHOLD,
            self.current_threshold - self.REDUCTION_STEP
        )
        self.attempts += 1
        self.is_active = True
        
        current_app.logger.info(
            f'Compromise mode: Reducing threshold to {self.current_threshold}% '
            f'(attempt {self.attempts})'
        )
        
        return self.current_threshold
    
    def limit_results(self, results: List) -> List:
        """
        Limit the number of results when in compromise mode.
        
        Args:
            results: List of results to limit
            
        Returns:
            Limited list (max 3 items) if in compromise mode, otherwise unchanged
        """
        if self.is_active and len(results) > self.MAX_RESULTS_IN_COMPROMISE:
            current_app.logger.info(
                f'Compromise mode: Limiting results from {len(results)} to '
                f'{self.MAX_RESULTS_IN_COMPROMISE}'
            )
            return results[:self.MAX_RESULTS_IN_COMPROMISE]
        return results
    
    def get_status(self) -> dict:
        """
        Get the current status of compromise mode.
        
        Returns:
            Dictionary with status information
        """
        return {
            'is_active': self.is_active,
            'initial_threshold': self.initial_threshold,
            'current_threshold': self.current_threshold,
            'attempts': self.attempts,
            'can_continue': self.should_continue()
        }


def search_with_compromise(search_function, query_text: str, initial_threshold: float, **kwargs) -> tuple:
    """
    Execute a search with automatic compromise mode fallback.
    
    This function wraps a search function and automatically retries with
    progressively lower thresholds if no results are found.
    
    Args:
        search_function: The search function to call (should accept min_similarity_score parameter)
        query_text: The search query text
        initial_threshold: Starting similarity threshold (0-100%)
        **kwargs: Additional arguments to pass to the search function
        
    Returns:
        Tuple of (results, compromise_info) where:
        - results: List of search results
        - compromise_info: Dictionary with compromise mode status
    """
    compromise = CompromiseMode(initial_threshold)
    
    current_app.logger.info(
        f'Starting search with initial threshold: {initial_threshold}%'
    )
    
    # First attempt with initial threshold
    results = search_function(
        query_text,
        min_similarity_score=initial_threshold,
        **kwargs
    )
    
    # If we have results, return them immediately
    if results:
        current_app.logger.info(
            f'Found {len(results)} results at initial threshold {initial_threshold}%'
        )
        return results, compromise.get_status()
    
    # No results - enter compromise mode
    current_app.logger.info(
        f'No results found at {initial_threshold}%, entering compromise mode'
    )
    
    # Keep trying with reduced thresholds
    while compromise.should_continue():
        new_threshold = compromise.reduce_threshold()
        
        results = search_function(
            query_text,
            min_similarity_score=new_threshold,
            **kwargs
        )
        
        if results:
            current_app.logger.info(
                f'Compromise mode SUCCESS: Found {len(results)} results at {new_threshold}%'
            )
            # Limit results to 3 in compromise mode
            results = compromise.limit_results(results)
            return results, compromise.get_status()
    
    # Reached minimum threshold with no results
    current_app.logger.info(
        f'Compromise mode exhausted: No results found even at {compromise.MIN_THRESHOLD}%'
    )
    
    return [], compromise.get_status()
