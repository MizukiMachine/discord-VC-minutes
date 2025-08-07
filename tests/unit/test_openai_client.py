import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from typing import List, Optional

from services.summary.openai_client import OpenAIClient, SummaryRequest, SummaryResponse
from framework.interfaces.core import CoreService


class TestOpenAIClient:
    """OpenAI API Client test suite for LLM summarization"""

    @pytest.fixture
    def mock_core_service(self) -> Mock:
        mock = Mock(spec=CoreService)
        mock.get_config.return_value = None
        mock.info = Mock()
        mock.error = Mock()
        mock.debug = Mock()
        mock.warning = Mock()
        return mock

    @pytest.fixture
    def mock_requests(self) -> Mock:
        with patch('services.summary.openai_client.requests') as mock:
            yield mock

    @pytest.fixture
    def openai_client(self, mock_core_service) -> OpenAIClient:
        return OpenAIClient(
            core_service=mock_core_service,
            api_key="test-api-key",
            model="gpt-4o-mini"
        )

    def test_client_initialization(self, openai_client):
        """Test OpenAI client initialization with API key and model"""
        assert openai_client.api_key == "test-api-key"
        assert openai_client.model == "gpt-4o-mini"
        assert openai_client.max_tokens == 2000
        assert openai_client.base_url == "https://api.openai.com/v1"

    def test_single_stage_summarization_success(self, openai_client, mock_requests):
        """Test successful single-stage summarization for short text"""
        text = "短いテキストの議事録内容です。" * 10
        expected_summary = "これは要約されたテキストです。"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": expected_summary}}],
            "usage": {"total_tokens": 150}
        }
        mock_requests.post.return_value = mock_response
        
        result = openai_client.summarize(text)
        
        assert isinstance(result, SummaryResponse)
        assert result.summary == expected_summary
        assert result.total_tokens == 150
        assert result.stages == 1
        assert result.success is True

    def test_two_stage_summarization_for_long_text(self, openai_client, mock_requests):
        """Test two-stage summarization when text exceeds token limit"""
        long_text = "長い議事録テキストです。" * 200  # Simulates >2000 tokens
        partial_summary = "部分要約1\n\n部分要約2"
        final_summary = "最終統合要約"
        
        # Mock token counting to trigger two-stage
        with patch.object(openai_client, '_estimate_tokens', return_value=2500):
            # Mock _chunk_text to return single chunk for simplicity
            with patch.object(openai_client, '_chunk_text', return_value=[long_text]):
                mock_response_1 = Mock()
                mock_response_1.status_code = 200  
                mock_response_1.json.return_value = {
                    "choices": [{"message": {"content": partial_summary}}],
                    "usage": {"total_tokens": 800}
                }
                
                mock_response_2 = Mock()
                mock_response_2.status_code = 200
                mock_response_2.json.return_value = {
                    "choices": [{"message": {"content": final_summary}}],
                    "usage": {"total_tokens": 300}
                }
                
                mock_requests.post.side_effect = [mock_response_1, mock_response_2]
                
                result = openai_client.summarize(long_text)
                
                assert result.summary == final_summary
                assert result.total_tokens == 1100  # 800 + 300
                assert result.stages == 2
                assert result.success is True

    def test_api_error_handling(self, openai_client, mock_requests):
        """Test handling of OpenAI API errors"""
        text = "テストテキスト"
        
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": {"message": "Rate limit exceeded"}}
        mock_requests.post.return_value = mock_response
        
        result = openai_client.summarize(text)
        
        assert result.success is False
        assert result.error_message == "Rate limit exceeded"
        assert result.summary == ""
        openai_client.core_service.error.assert_called_once()

    def test_connection_error_handling(self, openai_client, mock_requests):
        """Test handling of connection errors"""
        text = "テストテキスト"
        
        mock_requests.post.side_effect = Exception("Connection failed")
        
        result = openai_client.summarize(text)
        
        assert result.success is False
        assert "Connection failed" in result.error_message
        assert result.summary == ""

    def test_invalid_json_response_handling(self, openai_client, mock_requests):
        """Test handling of invalid JSON responses"""
        text = "テストテキスト"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_requests.post.return_value = mock_response
        
        result = openai_client.summarize(text)
        
        assert result.success is False
        assert "JSON decode error" in result.error_message

    def test_token_estimation(self, openai_client):
        """Test token estimation for text length"""
        short_text = "短いテキスト"
        long_text = "長いテキストです。" * 100
        
        short_tokens = openai_client._estimate_tokens(short_text)
        long_tokens = openai_client._estimate_tokens(long_text)
        
        assert short_tokens < long_tokens
        assert isinstance(short_tokens, int)
        assert isinstance(long_tokens, int)

    def test_text_chunking_for_two_stage_summary(self, openai_client):
        """Test text chunking logic for two-stage summarization"""
        long_text = "段落1です。\n\n段落2です。\n\n段落3です。\n\n段落4です。"
        
        chunks = openai_client._chunk_text(long_text, max_chunk_tokens=50)
        
        assert len(chunks) >= 1
        assert all(isinstance(chunk, str) for chunk in chunks)
        assert "".join(chunks).replace("\n\n---CHUNK_SEPARATOR---\n\n", "") in long_text

    def test_summary_request_validation(self, openai_client):
        """Test input validation for summary requests"""
        # Test empty text
        result = openai_client.summarize("")
        assert result.success is False
        assert "empty" in result.error_message.lower()
        
        # Test None text
        result = openai_client.summarize(None)
        assert result.success is False

    def test_custom_model_and_parameters(self, mock_core_service):
        """Test client with custom model and parameters"""
        client = OpenAIClient(
            core_service=mock_core_service,
            api_key="test-key",
            model="gpt-4",
            max_tokens=4000,
            temperature=0.3
        )
        
        assert client.model == "gpt-4"
        assert client.max_tokens == 4000
        assert client.temperature == 0.3

    def test_japanese_summarization_prompt(self, openai_client, mock_requests):
        """Test that Japanese summarization prompt is correctly formatted"""
        text = "テスト議事録内容"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "要約結果"}}],
            "usage": {"total_tokens": 100}
        }
        mock_requests.post.return_value = mock_response
        
        openai_client.summarize(text)
        
        # Verify the request was made with Japanese prompt
        call_args = mock_requests.post.call_args
        request_data = json.loads(call_args[1]['data'])
        
        assert "300-500字" in str(request_data['messages'])
        assert "日本語" in str(request_data['messages'])
        assert "議事録" in str(request_data['messages'])

    def test_timeout_configuration(self, openai_client, mock_requests):
        """Test API request timeout configuration"""
        text = "テストテキスト"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "要約"}}],
            "usage": {"total_tokens": 50}
        }
        mock_requests.post.return_value = mock_response
        
        openai_client.summarize(text)
        
        call_args = mock_requests.post.call_args
        assert 'timeout' in call_args[1]
        assert call_args[1]['timeout'] == 30