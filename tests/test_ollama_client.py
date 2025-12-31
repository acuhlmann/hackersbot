"""Tests for the Ollama client module"""

import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock
from src.models.ollama_client import OllamaClient


class TestOllamaClientInitialization:
    """Tests for OllamaClient initialization"""
    
    def test_default_initialization(self):
        """Test default initialization with environment defaults"""
        with patch.dict(os.environ, {}, clear=True):
            client = OllamaClient()
            
            assert client.base_url == "http://localhost:11434"
            assert client.summarizer_model == "qwen2.5:7b"
            assert client.filter_model == "qwen2.5:7b"
            assert client.general_model == "qwen2.5:latest"
    
    def test_custom_initialization(self):
        """Test initialization with custom values"""
        client = OllamaClient(
            base_url="http://custom:8080",
            summarizer_model="custom-model-1",
            filter_model="custom-model-2",
            general_model="custom-model-3"
        )
        
        assert client.base_url == "http://custom:8080"
        assert client.summarizer_model == "custom-model-1"
        assert client.filter_model == "custom-model-2"
        assert client.general_model == "custom-model-3"
    
    def test_environment_variable_override(self):
        """Test that environment variables override defaults"""
        env_vars = {
            "OLLAMA_BASE_URL": "http://env:9999",
            "OLLAMA_SUMMARIZER_MODEL": "env-summarizer",
            "OLLAMA_FILTER_MODEL": "env-filter",
            "OLLAMA_GENERAL_MODEL": "env-general"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            client = OllamaClient()
            
            assert client.base_url == "http://env:9999"
            assert client.summarizer_model == "env-summarizer"
            assert client.filter_model == "env-filter"
            assert client.general_model == "env-general"
    
    def test_llm_instances_initially_none(self):
        """Test that LLM instances are not created during init"""
        client = OllamaClient()
        
        assert client._summarizer_llm is None
        assert client._filter_llm is None
        assert client._general_llm is None


class TestOllamaClientLLMGetters:
    """Tests for LLM getter methods"""
    
    @pytest.fixture
    def client(self):
        """Create OllamaClient instance"""
        return OllamaClient()
    
    @patch('src.models.ollama_client.Ollama')
    def test_get_summarizer_llm_creates_once(self, mock_ollama_class, client):
        """Test that get_summarizer_llm creates LLM only once"""
        mock_llm = Mock()
        mock_ollama_class.return_value = mock_llm
        
        # Call twice
        llm1 = client.get_summarizer_llm()
        llm2 = client.get_summarizer_llm()
        
        # Should only create once
        assert mock_ollama_class.call_count == 1
        assert llm1 is llm2
    
    @patch('src.models.ollama_client.Ollama')
    def test_get_filter_llm_creates_once(self, mock_ollama_class, client):
        """Test that get_filter_llm creates LLM only once"""
        mock_llm = Mock()
        mock_ollama_class.return_value = mock_llm
        
        llm1 = client.get_filter_llm()
        llm2 = client.get_filter_llm()
        
        assert mock_ollama_class.call_count == 1
        assert llm1 is llm2
    
    @patch('src.models.ollama_client.Ollama')
    def test_get_general_llm_creates_once(self, mock_ollama_class, client):
        """Test that get_general_llm creates LLM only once"""
        mock_llm = Mock()
        mock_ollama_class.return_value = mock_llm
        
        llm1 = client.get_general_llm()
        llm2 = client.get_general_llm()
        
        assert mock_ollama_class.call_count == 1
        assert llm1 is llm2
    
    @patch('src.models.ollama_client.Ollama')
    def test_summarizer_llm_temperature(self, mock_ollama_class, client):
        """Test that summarizer LLM uses correct temperature"""
        client.get_summarizer_llm()
        
        call_kwargs = mock_ollama_class.call_args[1]
        assert call_kwargs["temperature"] == 0.3
    
    @patch('src.models.ollama_client.Ollama')
    def test_filter_llm_temperature(self, mock_ollama_class, client):
        """Test that filter LLM uses correct temperature"""
        client.get_filter_llm()
        
        call_kwargs = mock_ollama_class.call_args[1]
        assert call_kwargs["temperature"] == 0.1
    
    @patch('src.models.ollama_client.Ollama')
    def test_general_llm_temperature(self, mock_ollama_class, client):
        """Test that general LLM uses correct temperature"""
        client.get_general_llm()
        
        call_kwargs = mock_ollama_class.call_args[1]
        assert call_kwargs["temperature"] == 0.7


class TestOllamaClientSummarize:
    """Tests for summarize method"""
    
    @pytest.fixture
    def client(self):
        """Create OllamaClient with mocked LLM"""
        client = OllamaClient()
        mock_llm = Mock()
        mock_llm.invoke.return_value = "  Test summary  "
        client._summarizer_llm = mock_llm
        return client
    
    def test_summarize_basic(self, client):
        """Test basic summarization"""
        result = client.summarize("Some text to summarize")
        
        assert result == "Test summary"  # Should be stripped
        client._summarizer_llm.invoke.assert_called_once()
    
    def test_summarize_with_max_length(self, client):
        """Test summarization with max_length hint"""
        client.summarize("Some text", max_length=100)
        
        # Verify prompt includes max_length
        call_args = client._summarizer_llm.invoke.call_args[0][0]
        assert "100 words" in call_args
    
    def test_summarize_without_max_length(self, client):
        """Test summarization without max_length hint"""
        client.summarize("Some text")
        
        # Verify prompt doesn't include word limit
        call_args = client._summarizer_llm.invoke.call_args[0][0]
        assert "words" not in call_args or "100 words" not in call_args


class TestOllamaClientClassifyAI:
    """Tests for classify_ai_topic method"""
    
    @pytest.fixture
    def client(self):
        """Create OllamaClient with mocked LLM"""
        client = OllamaClient()
        mock_llm = Mock()
        client._filter_llm = mock_llm
        return client
    
    def test_classify_ai_topic_positive(self, client):
        """Test AI classification returns positive result"""
        client._filter_llm.invoke.return_value = json.dumps({
            "is_ai_related": True,
            "confidence": 0.95,
            "reasoning": "About machine learning"
        })
        
        result = client.classify_ai_topic(
            title="Machine Learning Tutorial",
            url="https://example.com",
            content="This is about neural networks"
        )
        
        assert result["is_ai_related"] is True
        assert result["confidence"] == 0.95
        assert "reasoning" in result
    
    def test_classify_ai_topic_negative(self, client):
        """Test AI classification returns negative result"""
        client._filter_llm.invoke.return_value = json.dumps({
            "is_ai_related": False,
            "confidence": 0.1,
            "reasoning": "About cooking"
        })
        
        result = client.classify_ai_topic(
            title="Best Pasta Recipes",
            url="https://example.com",
            content="How to make pasta"
        )
        
        assert result["is_ai_related"] is False
        assert result["confidence"] == 0.1
    
    def test_classify_ai_topic_json_in_code_block(self, client):
        """Test handling JSON wrapped in markdown code blocks"""
        client._filter_llm.invoke.return_value = """```json
{"is_ai_related": true, "confidence": 0.9, "reasoning": "AI content"}
```"""
        
        result = client.classify_ai_topic(
            title="Test",
            url="https://example.com"
        )
        
        assert result["is_ai_related"] is True
        assert result["confidence"] == 0.9
    
    def test_classify_ai_topic_fallback_on_parse_error(self, client):
        """Test fallback behavior when JSON parsing fails"""
        client._filter_llm.invoke.return_value = "This is about artificial intelligence and machine learning"
        
        result = client.classify_ai_topic(
            title="Test",
            url="https://example.com"
        )
        
        # Should infer from text
        assert result["is_ai_related"] is True  # Contains "artificial intelligence"
        assert result["confidence"] == 0.5
        assert "inferred" in result["reasoning"].lower()
    
    def test_classify_ai_topic_fallback_not_ai(self, client):
        """Test fallback returns false when no AI keywords"""
        client._filter_llm.invoke.return_value = "This is about cooking pasta"
        
        result = client.classify_ai_topic(
            title="Test",
            url="https://example.com"
        )
        
        assert result["is_ai_related"] is False
    
    def test_classify_ai_topic_truncates_content(self, client):
        """Test that long content is truncated"""
        long_content = "A" * 1000
        
        client._filter_llm.invoke.return_value = json.dumps({
            "is_ai_related": True,
            "confidence": 0.9,
            "reasoning": "Test"
        })
        
        client.classify_ai_topic(
            title="Test",
            url="https://example.com",
            content=long_content
        )
        
        # Verify content was truncated in prompt
        call_args = client._filter_llm.invoke.call_args[0][0]
        assert len(call_args) < len(long_content) + 500


class TestOllamaClientGenerate:
    """Tests for generate method"""
    
    @pytest.fixture
    def client(self):
        """Create OllamaClient with mocked LLMs"""
        client = OllamaClient()
        
        client._summarizer_llm = Mock()
        client._summarizer_llm.invoke.return_value = "  Summarizer response  "
        
        client._filter_llm = Mock()
        client._filter_llm.invoke.return_value = "  Filter response  "
        
        client._general_llm = Mock()
        client._general_llm.invoke.return_value = "  General response  "
        
        return client
    
    def test_generate_with_summarizer_model(self, client):
        """Test generate using summarizer model"""
        result = client.generate("Test prompt", model_type="summarizer")
        
        assert result == "Summarizer response"
        client._summarizer_llm.invoke.assert_called_once_with("Test prompt")
    
    def test_generate_with_filter_model(self, client):
        """Test generate using filter model"""
        result = client.generate("Test prompt", model_type="filter")
        
        assert result == "Filter response"
        client._filter_llm.invoke.assert_called_once_with("Test prompt")
    
    def test_generate_with_general_model(self, client):
        """Test generate using general model"""
        result = client.generate("Test prompt", model_type="general")
        
        assert result == "General response"
        client._general_llm.invoke.assert_called_once_with("Test prompt")
    
    def test_generate_default_model(self, client):
        """Test generate defaults to general model"""
        result = client.generate("Test prompt")
        
        assert result == "General response"
        client._general_llm.invoke.assert_called_once()
    
    def test_generate_unknown_model_uses_general(self, client):
        """Test that unknown model type falls back to general"""
        result = client.generate("Test prompt", model_type="unknown")
        
        assert result == "General response"


class TestOllamaClientIntegration:
    """Integration-style tests (still mocked but testing interaction)"""
    
    @patch('src.models.ollama_client.Ollama')
    def test_full_workflow(self, mock_ollama_class):
        """Test a full workflow using the client"""
        mock_llm = Mock()
        mock_llm.invoke.return_value = json.dumps({
            "is_ai_related": True,
            "confidence": 0.9,
            "reasoning": "AI content"
        })
        mock_ollama_class.return_value = mock_llm
        
        client = OllamaClient()
        
        # Classify an article
        result = client.classify_ai_topic(
            title="GPT-4 Tutorial",
            url="https://example.com",
            content="Learn about GPT-4"
        )
        
        assert result["is_ai_related"] is True
        
        # Summarize content
        mock_llm.invoke.return_value = "This is a summary about AI"
        summary = client.summarize("Long text about AI...")
        
        assert "summary" in summary.lower() or "AI" in summary
