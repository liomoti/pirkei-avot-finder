"""
Unit tests for AWS Semantic Search Client - Network Error Handling

This test module focuses on testing network error handling scenarios:
- Timeout handling
- Network connectivity failure

Validates: Requirements 3.1, 3.4
"""

import unittest
from unittest.mock import patch, Mock
import requests
from api.aws_search_client import AWSSemanticSearchClient, AWSSearchError


class TestAWSSearchClientNetworkErrors(unittest.TestCase):
    """Test suite for network error handling in AWS search client."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test-api-key-12345"
        self.api_url = "https://test-api.example.com/search"
        self.client = AWSSemanticSearchClient(self.api_key, self.api_url)
    
    @patch('api.aws_search_client.requests.post')
    def test_timeout_handling(self, mock_post):
        """
        Test that timeout errors are handled gracefully.
        
        Validates: Requirements 3.1
        
        When the API request times out, the client should:
        1. Catch the Timeout exception
        2. Log the error
        3. Raise AWSSearchError with appropriate message
        """
        # Arrange: Configure mock to raise Timeout exception
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")
        
        # Act & Assert: Verify AWSSearchError is raised
        with self.assertRaises(AWSSearchError) as context:
            self.client._make_api_request("test query")
        
        # Verify error message indicates timeout
        self.assertIn("timed out", str(context.exception).lower())
        
        # Verify the request was attempted with correct parameters
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Verify headers include API key
        self.assertEqual(call_args.kwargs['headers']['x-api-key'], self.api_key)
        self.assertEqual(call_args.kwargs['headers']['Content-Type'], 'application/json')
        
        # Verify timeout was set
        self.assertEqual(call_args.kwargs['timeout'], self.client.timeout)
    
    @patch('api.aws_search_client.requests.post')
    def test_network_connectivity_failure(self, mock_post):
        """
        Test that network connectivity failures are handled gracefully.
        
        Validates: Requirements 3.4
        
        When network connectivity fails, the client should:
        1. Catch the ConnectionError exception
        2. Log the error
        3. Raise AWSSearchError with appropriate message
        """
        # Arrange: Configure mock to raise ConnectionError
        mock_post.side_effect = requests.exceptions.ConnectionError(
            "Failed to establish connection"
        )
        
        # Act & Assert: Verify AWSSearchError is raised
        with self.assertRaises(AWSSearchError) as context:
            self.client._make_api_request("test query")
        
        # Verify error message indicates network connectivity issue
        self.assertIn("connectivity", str(context.exception).lower())
        
        # Verify the request was attempted
        mock_post.assert_called_once()
    
    @patch('api.aws_search_client.requests.post')
    def test_timeout_in_search_method(self, mock_post):
        """
        Test that timeout errors in the search method are propagated correctly.
        
        Validates: Requirements 3.1
        
        The search() method should propagate AWSSearchError from _make_api_request.
        """
        # Arrange: Configure mock to raise Timeout exception
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")
        
        # Act & Assert: Verify AWSSearchError is raised from search method
        with self.assertRaises(AWSSearchError) as context:
            self.client.search("test query")
        
        # Verify error message indicates timeout
        self.assertIn("timed out", str(context.exception).lower())
    
    @patch('api.aws_search_client.requests.post')
    def test_connection_error_in_search_method(self, mock_post):
        """
        Test that connection errors in the search method are propagated correctly.
        
        Validates: Requirements 3.4
        
        The search() method should propagate AWSSearchError from _make_api_request.
        """
        # Arrange: Configure mock to raise ConnectionError
        mock_post.side_effect = requests.exceptions.ConnectionError(
            "Network unreachable"
        )
        
        # Act & Assert: Verify AWSSearchError is raised from search method
        with self.assertRaises(AWSSearchError) as context:
            self.client.search("test query")
        
        # Verify error message indicates connectivity issue
        self.assertIn("connectivity", str(context.exception).lower())


if __name__ == '__main__':
    unittest.main()
