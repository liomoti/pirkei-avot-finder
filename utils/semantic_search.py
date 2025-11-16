"""
Semantic Search Module for Mishna Text

This module handles semantic similarity search using sentence transformers
and vector embeddings. It provides intelligent result filtering based on
adaptive thresholds and distance gap analysis.

Key Components:
1. Query encoding using AlephBERT model
2. Vector similarity search using PostgreSQL pgvector
3. Adaptive threshold calculation based on result quality
4. Gap analysis to find natural cutoff points in results
"""

from typing import List, Tuple, Optional
from flask import current_app
from sqlalchemy import text
from sentence_transformers import SentenceTransformer

from models import db, Mishna, Tag
from utils.compromise_mode import search_with_compromise


class SemanticSearchEngine:
    """
    Handles semantic search operations for Mishna texts using vector embeddings.
    
    The engine uses a pre-trained Hebrew language model (AlephBERT) to encode
    queries and find semantically similar texts in the database.
    """
    
    # Words to ignore when encoding queries
    IGNORE_WORDS = [
        'את', 'של', 'על', 'אל', 'מה', 'זה', 'זו', 'זאת', 'אלה', 'אלו',
        'כל', 'כי', 'אם', 'או', 'גם', 'רק', 'עם', 'לפי', 'אצל',
         'משניות', 'משנה',
    ]
    
    # Minimum similarity score threshold (0-100%)
    MIN_SIMILARITY_SCORE = 85
    
    def __init__(self, model: SentenceTransformer):
        """
        Initialize the semantic search engine.
        
        Args:
            model: Pre-trained SentenceTransformer model for encoding text
        """
        self.model = model
        self.tag_boost_weight = 0.1  # How much to reduce distance for matching tags
    
    def search(self, query_text: str, max_candidates: int = 30, min_similarity_score: Optional[float] = None) -> List[Mishna]:
        """
        Perform semantic search for the given query text.
        
        Args:
            query_text: The search query in natural language
            max_candidates: Maximum number of candidates to retrieve from database
            min_similarity_score: Optional minimum similarity percentage (0-100%) - 
                                 filters out results with similarity below this threshold.
                                 Higher values = stricter filtering (e.g., 70 means 70% similarity minimum)
            
        Returns:
            List of Mishna objects with similarity_score attribute attached
        """
        if not query_text or not query_text.strip():
            current_app.logger.info('Empty semantic query, returning no results')
            return []
        
        # Use class parameter if not provided
        if min_similarity_score is None:
            min_similarity_score = self.MIN_SIMILARITY_SCORE
        
        try:
            # Step 1: Encode query to vector
            query_vector = self._encode_query(query_text)
            
            # Step 2: Find similar tags
            similar_tags = self._find_similar_tags(query_vector)
            
            # Step 3: Retrieve candidates from database
            candidates, all_distances = self._retrieve_candidates(query_vector, max_candidates)
            
            # Step 4: Apply tag-based boosting
            boosted_candidates = self._apply_tag_boost(candidates, similar_tags)
            
            # Step 5: Calculate adaptive threshold (using original distances)
            cutoff_distance = self._calculate_threshold(all_distances)
            
            # Step 6: Filter and return results (using boosted scores)
            results = self._filter_results(boosted_candidates, cutoff_distance, min_similarity_score)
            
            current_app.logger.info(f'Returned {len(results)} results (threshold: {cutoff_distance:.4f})')
            return results
            
        except Exception as e:
            current_app.logger.error(f'Error in semantic search: {str(e)}', exc_info=True)
            return []
    
    def search_with_compromise(self, query_text: str, max_candidates: int = 30) -> tuple:
        """
        Perform semantic search with automatic compromise mode fallback.
        
        If no results are found at the initial MIN_SIMILARITY_SCORE threshold,
        this method automatically reduces the threshold by 5% increments until
        results are found or the threshold reaches 30%.
        
        In compromise mode, results are limited to a maximum of 3 items.
        
        Args:
            query_text: The search query in natural language
            max_candidates: Maximum number of candidates to retrieve from database
            
        Returns:
            Tuple of (results, compromise_info) where:
            - results: List of Mishna objects with similarity_score attribute
            - compromise_info: Dictionary with compromise mode status information
        """
        return search_with_compromise(
            search_function=self.search,
            query_text=query_text,
            initial_threshold=self.MIN_SIMILARITY_SCORE,
            max_candidates=max_candidates
        )
    
    def _encode_query(self, query_text: str) -> list:
        """
        Encode the query text into a vector embedding.
        
        Filters out words from the ignore list before encoding.
        
        Args:
            query_text: The text to encode
            
        Returns:
            List representation of the query vector
        """
        # Remove words from ignore list
        words = query_text.split()
        filtered_words = [word for word in words if word.lower() not in self.IGNORE_WORDS]
        filtered_text = ' '.join(filtered_words)
        
        current_app.logger.info(f'Original query text: "{query_text}"')
        current_app.logger.info(f'Filtered query text: "{filtered_text}"')
        current_app.logger.info(
            f'Encoding query: original length={len(query_text)} chars, '
            f'filtered length={len(filtered_text)} chars'
        )
        
        # Use filtered text for encoding, or original if filtering removed everything
        text_to_encode = filtered_text if filtered_text.strip() else query_text
        query_vector = self.model.encode(text_to_encode)
        return query_vector.tolist()
    
    def _find_similar_tags(self, query_vector: list, max_tags: int = 3) -> List[int]:
        """
        Find tags that are semantically similar to the query.
        
        Args:
            query_vector: The encoded query vector
            max_tags: Maximum number of similar tags to return (1-3)
            
        Returns:
            List of tag IDs that are similar to the query
        """
        try:
            # Get all tags with their names
            all_tags = Tag.query.all()
            
            if not all_tags:
                current_app.logger.info('No tags found in database')
                return []
            
            # Encode all tag names in smaller batches to reduce memory usage
            tag_names = [tag.name for tag in all_tags]
            batch_size = 10
            tag_vectors = []
            
            for i in range(0, len(tag_names), batch_size):
                batch = tag_names[i:i + batch_size]
                batch_vectors = self.model.encode(batch, show_progress_bar=False)
                tag_vectors.extend(batch_vectors)
            
            # Calculate cosine distances between query and each tag
            from numpy import dot
            from numpy.linalg import norm
            
            distances = []
            for i, tag_vector in enumerate(tag_vectors):
                # Cosine distance = 1 - cosine similarity
                cosine_sim = dot(query_vector, tag_vector) / (norm(query_vector) * norm(tag_vector))
                distance = 1 - cosine_sim
                distances.append((distance, all_tags[i].id, all_tags[i].name))
            
            # Sort by distance (lower is better) and take top max_tags
            distances.sort(key=lambda x: x[0])
            similar_tags = distances[:max_tags]
            
            # Only include tags with reasonable similarity (distance < 0.7)
            similar_tag_ids = [tag_id for dist, tag_id, name in similar_tags if dist < 0.7]
            
            if similar_tag_ids:
                tag_info = [(name, dist) for dist, tag_id, name in similar_tags if dist < 0.7]
                current_app.logger.info(f'Found {len(similar_tag_ids)} similar tags: {tag_info}')
            else:
                current_app.logger.info('No sufficiently similar tags found')
            
            return similar_tag_ids
            
        except Exception as e:
            current_app.logger.error(f'Error finding similar tags: {str(e)}', exc_info=True)
            return []
    
    def _apply_tag_boost(
        self, 
        candidates: List[Tuple[float, Mishna]], 
        similar_tag_ids: List[int]
    ) -> List[Tuple[float, Mishna]]:
        """
        Apply boosting to mishnas that have tags matching the similar tags.
        
        Mishnas with matching tags get their distance reduced (better score).
        
        Args:
            candidates: List of (distance, Mishna) tuples
            similar_tag_ids: List of tag IDs that are similar to the query
            
        Returns:
            List of (boosted_distance, Mishna) tuples
        """
        if not similar_tag_ids:
            current_app.logger.info('No similar tags to apply boost')
            return candidates
        
        boosted_candidates = []
        
        for distance, mishna in candidates:
            # Check if mishna has any of the similar tags
            mishna_tag_ids = {tag.id for tag in mishna.tags}
            matching_tags = mishna_tag_ids.intersection(similar_tag_ids)
            
            if matching_tags:
                # Calculate boost based on number of matching tags
                # More matching tags = stronger boost
                boost_amount = len(matching_tags) * self.tag_boost_weight
                boosted_distance = min(100, max(0, distance - boost_amount))
                
                current_app.logger.info(
                    f'Mishna {mishna.id}: original distance={distance:.4f}, '
                    f'boosted distance={boosted_distance:.4f} '
                    f'(matched {len(matching_tags)} tags)'
                )
                
                boosted_candidates.append((boosted_distance, mishna))
            else:
                boosted_candidates.append((distance, mishna))
        
        # Re-sort by boosted distance
        boosted_candidates.sort(key=lambda x: x[0])
        
        return boosted_candidates
    
    def _retrieve_candidates(
        self, 
        query_vector: list, 
        max_candidates: int
    ) -> Tuple[List[Tuple[float, Mishna]], List[float]]:
        """
        Retrieve candidate Mishnas from database using vector similarity.
        
        Uses PostgreSQL's pgvector extension with cosine distance operator (<=>)
        to find the most similar texts.
        
        Args:
            query_vector: The encoded query vector
            max_candidates: Maximum number of candidates to retrieve
            
        Returns:
            Tuple of (candidates list, all distances list)
            - candidates: List of (distance, Mishna) tuples
            - all_distances: List of all distance values for analysis
        """
        sql = text('''
            SELECT *, (embedding <=> (:query_vector)::vector) as distance 
            FROM mishna 
            ORDER BY distance 
            LIMIT :limit
        ''')
        
        result_proxy = db.session.execute(
            sql, 
            {"query_vector": query_vector, "limit": max_candidates}
        )
        
        candidates = []
        all_distances = []
        
        for row in result_proxy:
            distance = row.distance
            all_distances.append(distance)
            
            mishna = Mishna.query.get(row.id)
            if mishna:
                candidates.append((distance, mishna))
        
        current_app.logger.info(f'Total candidates retrieved: {len(candidates)}')
        if all_distances:
            current_app.logger.info(
                f'Distance range: {min(all_distances):.4f} to {max(all_distances):.4f}'
            )
        
        return candidates, all_distances
    
    def _calculate_threshold(self, all_distances: List[float]) -> float:
        """
        Calculate adaptive threshold for filtering results.
        
        Returns a fixed threshold based on the quality of the best match.
        All results below this threshold will be returned.
        
        Strategy:
        - Better matches → stricter threshold (fewer irrelevant results)
        - Worse matches → more lenient threshold (more potential matches)
        
        Args:
            all_distances: List of all candidate distances
            
        Returns:
            The calculated cutoff distance threshold
        """
        # Default threshold for edge cases
        if not all_distances:
            return 0.70
        
        min_distance = min(all_distances)
        
        # Determine threshold based on best match quality
        thresholds = self._get_quality_thresholds(min_distance)
        cutoff_distance = thresholds['base_max']
        
        current_app.logger.info(
            f'Min distance: {min_distance:.4f}, '
            f'using threshold: {cutoff_distance:.4f}'
        )
        
        return cutoff_distance
    
    def _get_quality_thresholds(self, min_distance: float) -> dict:
        """
        Get threshold based on minimum distance quality.
        
        Quality tiers:
        - Excellent (< 0.55): Strict filtering (0.65)
        - Good (0.55-0.60): Moderate filtering (0.68)
        - Decent (0.60-0.65): Lenient filtering (0.70)
        - Poor (> 0.65): Most lenient filtering (0.72)
        
        Args:
            min_distance: The smallest distance in the result set
            
        Returns:
            Dictionary with 'base_max' threshold value
        """
        if min_distance < 0.55:
            return {'base_max': 0.65}
        elif min_distance < 0.60:
            return {'base_max': 0.68}
        elif min_distance < 0.65:
            return {'base_max': 0.70}
        else:
            return {'base_max': 0.72}
    

    def _filter_results(
        self, 
        candidates: List[Tuple[float, Mishna]], 
        cutoff_distance: float,
        min_similarity_score: Optional[float] = None
    ) -> List[Mishna]:
        """
        Filter candidates based on threshold.
        
        Returns all results with distance <= cutoff_distance and similarity >= min_similarity_score.
        
        Args:
            candidates: List of (distance, Mishna) tuples
            cutoff_distance: The maximum threshold distance for filtering
            min_similarity_score: Optional minimum similarity percentage (0-100%) - 
                                 filters out results with similarity below this threshold
            
        Returns:
            List of filtered Mishna objects with similarity_score (as percentage) attached
        """
        results = []
        
        # Filter by threshold
        for distance, mishna in candidates:
            # Convert distance to similarity percentage (0-100%)
            # Using the same formula as in index.html: ((0.72 - distance) / 0.22 * 100)
            # This maps distance range [0.5, 0.72] to percentage range [100%, 0%]
            # Lower distance = higher similarity percentage
            similarity_percentage = ((0.72 - distance) / 0.22 * 100)
            # Clamp to 0-100 range
            similarity_percentage = max(0, min(100, similarity_percentage))
            
            # Apply both cutoff_distance (upper bound) and min_similarity_score (lower bound)
            if distance <= cutoff_distance:
                if min_similarity_score is None or similarity_percentage >= min_similarity_score:
                    mishna.similarity_score = similarity_percentage
                    results.append(mishna)
                    current_app.logger.info(
                        f"[OK] Mishna {mishna.id}: distance={distance:.4f}, similarity={similarity_percentage:.2f}%"
                    )
                else:
                    current_app.logger.info(
                        f"[FILTERED] Mishna {mishna.id}: distance={distance:.4f}, similarity={similarity_percentage:.2f}% "
                        f"(below min threshold {min_similarity_score:.2f}%)"
                    )
        
        # Log rejected candidates for debugging
        self._log_rejected_candidates(candidates, results, cutoff_distance)
        
        return results
    
    def _log_rejected_candidates(
        self, 
        candidates: List[Tuple[float, Mishna]], 
        results: List[Mishna],
        cutoff_distance: float
    ) -> None:
        """
        Log information about rejected candidates for debugging purposes.
        
        Args:
            candidates: All candidate results
            results: Accepted results
            cutoff_distance: The threshold used for filtering
        """
        result_ids = {m.id for m in results}
        rejected = [
            (d, m) for d, m in candidates 
            if d > cutoff_distance and m.id not in result_ids
        ]
        
        if rejected:
            current_app.logger.info(
                f'Rejected {len(rejected)} candidates (showing first 3):'
            )
            for i, (d, m) in enumerate(rejected[:3]):
                preview = m.text_raw[:40].replace('\r', '').replace('\n', ' ')
                current_app.logger.info(
                    f"  [REJECTED-{i+1}] distance={d:.4f}, text='{preview}...'"
                )
