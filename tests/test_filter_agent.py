"""Tests for the filter agent module"""

import pytest
from unittest.mock import Mock, patch
from src.agents.filter_agent import FilterAgent


class TestFilterAgent:
    """Tests for FilterAgent class"""
    
    @pytest.fixture
    def filter_agent(self, mock_llm_client):
        """Create FilterAgent with mocked LLMClient"""
        return FilterAgent(llm_client=mock_llm_client)
    
    def test_filter_agent_initialization_default(self):
        """Test FilterAgent creates LLMClient if not provided"""
        with patch('src.agents.filter_agent.get_llm_client') as mock_get_client:
            agent = FilterAgent()
            mock_get_client.assert_called_once_with()
    
    def test_filter_agent_initialization_custom_client(self, mock_llm_client):
        """Test FilterAgent uses provided LLMClient"""
        agent = FilterAgent(llm_client=mock_llm_client)
        assert agent.llm_client is mock_llm_client
    
    def test_classify_article_ai_related(self, filter_agent, sample_article_with_content):
        """Test classifying an AI-related article"""
        filter_agent.llm_client.classify_ai_topic.return_value = {
            "is_ai_related": True,
            "confidence": 0.95,
            "reasoning": "Article discusses AI and machine learning"
        }
        
        result = filter_agent.classify_article(sample_article_with_content)
        
        assert result["is_ai_related"] is True
        assert result["confidence"] == 0.95
        assert "reasoning" in result
    
    def test_classify_article_not_ai_related(self, filter_agent, sample_article):
        """Test classifying a non-AI article"""
        filter_agent.llm_client.classify_ai_topic.return_value = {
            "is_ai_related": False,
            "confidence": 0.1,
            "reasoning": "Article is about cooking"
        }
        
        result = filter_agent.classify_article(sample_article)
        
        assert result["is_ai_related"] is False
        assert result["confidence"] == 0.1
    
    def test_classify_article_calls_llm_client(self, filter_agent, sample_article_with_content):
        """Test that classify_article calls LLM client correctly"""
        filter_agent.classify_article(sample_article_with_content)
        
        filter_agent.llm_client.classify_ai_topic.assert_called_once_with(
            title=sample_article_with_content["title"],
            url=sample_article_with_content["url"],
            content=sample_article_with_content["content"]
        )
    
    def test_filter_ai_articles_all_pass(self, filter_agent, sample_article):
        """Test filtering when all articles are AI-related"""
        filter_agent.llm_client.classify_ai_topic.return_value = {
            "is_ai_related": True,
            "confidence": 0.9,
            "reasoning": "AI content"
        }
        
        articles = [sample_article.copy(), sample_article.copy()]
        result = filter_agent.filter_ai_articles(articles, min_confidence=0.5)
        
        assert len(result) == 2
        for article in result:
            assert "ai_classification" in article
    
    def test_filter_ai_articles_none_pass(self, filter_agent, sample_article):
        """Test filtering when no articles are AI-related"""
        filter_agent.llm_client.classify_ai_topic.return_value = {
            "is_ai_related": False,
            "confidence": 0.1,
            "reasoning": "Not AI"
        }
        
        articles = [sample_article.copy(), sample_article.copy()]
        result = filter_agent.filter_ai_articles(articles, min_confidence=0.5)
        
        assert len(result) == 0
    
    def test_filter_ai_articles_some_pass(self, filter_agent, sample_article):
        """Test filtering when some articles pass threshold"""
        # First article passes, second doesn't
        filter_agent.llm_client.classify_ai_topic.side_effect = [
            {"is_ai_related": True, "confidence": 0.9, "reasoning": "AI"},
            {"is_ai_related": True, "confidence": 0.3, "reasoning": "Maybe AI"}
        ]
        
        articles = [sample_article.copy(), sample_article.copy()]
        result = filter_agent.filter_ai_articles(articles, min_confidence=0.5)
        
        assert len(result) == 1
    
    def test_filter_ai_articles_confidence_threshold(self, filter_agent, sample_article):
        """Test that confidence threshold is respected"""
        filter_agent.llm_client.classify_ai_topic.return_value = {
            "is_ai_related": True,
            "confidence": 0.6,
            "reasoning": "AI content"
        }
        
        articles = [sample_article.copy()]
        
        # Should pass with 0.5 threshold
        result = filter_agent.filter_ai_articles(articles.copy(), min_confidence=0.5)
        assert len(result) == 1
        
        # Reset side effect for next call
        filter_agent.llm_client.classify_ai_topic.return_value = {
            "is_ai_related": True,
            "confidence": 0.6,
            "reasoning": "AI content"
        }
        
        # Should fail with 0.8 threshold
        result = filter_agent.filter_ai_articles(articles.copy(), min_confidence=0.8)
        assert len(result) == 0
    
    def test_filter_ai_articles_is_ai_false_with_high_confidence(self, filter_agent, sample_article):
        """Test that is_ai_related must be True regardless of confidence"""
        filter_agent.llm_client.classify_ai_topic.return_value = {
            "is_ai_related": False,
            "confidence": 0.99,
            "reasoning": "Definitely not AI but very confident"
        }
        
        articles = [sample_article.copy()]
        result = filter_agent.filter_ai_articles(articles, min_confidence=0.5)
        
        assert len(result) == 0
    
    def test_batch_classify_adds_metadata(self, filter_agent, sample_article):
        """Test batch_classify adds classification to all articles"""
        filter_agent.llm_client.classify_ai_topic.return_value = {
            "is_ai_related": True,
            "confidence": 0.8,
            "reasoning": "AI"
        }
        
        articles = [sample_article.copy(), sample_article.copy(), sample_article.copy()]
        result = filter_agent.batch_classify(articles)
        
        assert len(result) == 3
        for article in result:
            assert "ai_classification" in article
    
    def test_batch_classify_skips_already_classified(self, filter_agent, sample_article):
        """Test batch_classify skips articles that already have classification"""
        article1 = sample_article.copy()
        article1["ai_classification"] = {"is_ai_related": True, "confidence": 0.9}
        
        article2 = sample_article.copy()
        
        articles = [article1, article2]
        filter_agent.batch_classify(articles)
        
        # Should only call classify once (for article2)
        assert filter_agent.llm_client.classify_ai_topic.call_count == 1
    
    def test_classify_article_empty_content(self, filter_agent):
        """Test classifying article with no content"""
        article = {
            "title": "Test Article",
            "url": "https://example.com",
        }
        
        filter_agent.classify_article(article)
        
        # Should still call with empty string for content
        filter_agent.llm_client.classify_ai_topic.assert_called_once_with(
            title="Test Article",
            url="https://example.com",
            content=""
        )


class TestFilterAgentEdgeCases:
    """Edge case tests for FilterAgent"""
    
    @pytest.fixture
    def filter_agent(self, mock_llm_client):
        """Create FilterAgent with mocked LLMClient"""
        return FilterAgent(llm_client=mock_llm_client)
    
    def test_filter_empty_articles_list(self, filter_agent):
        """Test filtering empty article list"""
        result = filter_agent.filter_ai_articles([], min_confidence=0.5)
        assert result == []
    
    def test_batch_classify_empty_list(self, filter_agent):
        """Test batch classify with empty list"""
        result = filter_agent.batch_classify([])
        assert result == []
    
    def test_classify_article_minimal_data(self, filter_agent):
        """Test classifying article with minimal data"""
        article = {}
        
        filter_agent.classify_article(article)
        
        filter_agent.llm_client.classify_ai_topic.assert_called_once_with(
            title="",
            url="",
            content=""
        )
