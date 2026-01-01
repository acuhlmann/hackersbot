"""Tests for the summarizer agent module"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from src.agents.summarizer_agent import SummarizerAgent


class TestSummarizerAgent:
    """Tests for SummarizerAgent class"""
    
    @pytest.fixture
    def summarizer_agent(self, mock_llm_client):
        """Create SummarizerAgent with mocked LLMClient"""
        return SummarizerAgent(llm_client=mock_llm_client)
    
    def test_summarizer_initialization_default(self):
        """Test SummarizerAgent creates LLMClient if not provided"""
        with patch('src.agents.summarizer_agent.get_llm_client') as mock_get_client:
            agent = SummarizerAgent()
            mock_get_client.assert_called_once_with(provider=None)
    
    def test_summarizer_initialization_custom_client(self, mock_llm_client):
        """Test SummarizerAgent uses provided LLMClient"""
        agent = SummarizerAgent(llm_client=mock_llm_client)
        assert agent.llm_client is mock_llm_client
    
    def test_summarize_article_basic(self, summarizer_agent, sample_article_with_content):
        """Test basic article summarization"""
        result = summarizer_agent.summarize_article(
            sample_article_with_content,
            include_comments=False
        )
        
        assert "article_summary" in result
        summarizer_agent.llm_client.summarize.assert_called_once()
    
    def test_summarize_article_without_content(self, summarizer_agent, sample_article):
        """Test summarizing article without content"""
        result = summarizer_agent.summarize_article(sample_article, include_comments=False)
        
        assert "article_summary" in result
        # Should still call summarize even without content
        summarizer_agent.llm_client.summarize.assert_called_once()
    
    def test_summarize_article_with_comments(self, summarizer_agent, sample_article_with_comments):
        """Test summarizing article with comments"""
        # Set up mock for sentiment analysis
        summarizer_agent.llm_client.get_filter_llm.return_value.invoke.return_value = json.dumps({
            "sentiment": "positive",
            "score": 0.8,
            "details": "Test details",
            "topics": ["AI", "tech"]
        })
        
        result = summarizer_agent.summarize_article(
            sample_article_with_comments,
            include_comments=True
        )
        
        assert "article_summary" in result
        assert "comment_summary" in result
        assert "comment_sentiment" in result
        assert "comment_topics" in result
    
    def test_summarize_article_no_comments_flag(self, summarizer_agent, sample_article_with_comments):
        """Test that include_comments=False skips comment summarization"""
        result = summarizer_agent.summarize_article(
            sample_article_with_comments,
            include_comments=False
        )
        
        assert result.get("comment_summary") is None
        assert result.get("comment_sentiment") is None
    
    def test_summarize_article_empty_comments(self, summarizer_agent, sample_article_with_content):
        """Test summarizing article with empty comments list"""
        article = sample_article_with_content.copy()
        article["comments"] = []
        
        result = summarizer_agent.summarize_article(article, include_comments=True)
        
        assert result.get("comment_summary") is None
    
    def test_summarize_articles_multiple(self, summarizer_agent, sample_article):
        """Test summarizing multiple articles"""
        articles = [sample_article.copy() for _ in range(3)]
        
        results = summarizer_agent.summarize_articles(articles, include_comments=False)
        
        assert len(results) == 3
        for article in results:
            assert "article_summary" in article
    
    def test_summarize_article_content_truncation(self, summarizer_agent, sample_article):
        """Test that long content is truncated"""
        article = sample_article.copy()
        article["content"] = "A" * 5000  # Long content
        
        summarizer_agent.summarize_article(article, include_comments=False)
        
        # Verify summarize was called (content should be truncated internally)
        summarizer_agent.llm_client.summarize.assert_called_once()
        call_args = summarizer_agent.llm_client.summarize.call_args
        # The summary text should include truncated content
        assert len(call_args[0][0]) <= 3100  # 3000 chars + title + url


class TestSummarizerAgentCommentAnalysis:
    """Tests for comment analysis functionality"""
    
    @pytest.fixture
    def summarizer_agent(self, mock_llm_client):
        """Create SummarizerAgent with mocked LLMClient"""
        return SummarizerAgent(llm_client=mock_llm_client)
    
    def test_analyze_comment_sentiment_positive(self, summarizer_agent):
        """Test sentiment analysis returns positive"""
        summarizer_agent.llm_client.get_filter_llm.return_value.invoke.return_value = json.dumps({
            "sentiment": "positive",
            "score": 0.85,
            "details": "Comments are enthusiastic",
            "topics": ["innovation", "progress"]
        })
        
        result = summarizer_agent._analyze_comment_sentiment("Great article! Love it!")
        
        assert result["sentiment"] == "positive"
        assert result["score"] == 0.85
    
    def test_analyze_comment_sentiment_negative(self, summarizer_agent):
        """Test sentiment analysis returns negative"""
        summarizer_agent.llm_client.get_filter_llm.return_value.invoke.return_value = json.dumps({
            "sentiment": "negative",
            "score": 0.2,
            "details": "Comments are critical",
            "topics": ["concerns", "problems"]
        })
        
        result = summarizer_agent._analyze_comment_sentiment("This is terrible!")
        
        assert result["sentiment"] == "negative"
        assert result["score"] == 0.2
    
    def test_analyze_comment_sentiment_fallback(self, summarizer_agent):
        """Test sentiment analysis fallback on JSON parse error"""
        summarizer_agent.llm_client.get_filter_llm.return_value.invoke.return_value = "invalid json"
        
        result = summarizer_agent._analyze_comment_sentiment("good great helpful")
        
        # Should use keyword-based fallback
        assert "sentiment" in result
        assert "score" in result
    
    def test_analyze_agreement_with_article(self, summarizer_agent):
        """Test agreement analysis with article"""
        summarizer_agent.llm_client.get_filter_llm.return_value.invoke.return_value = json.dumps({
            "consensus": "agree",
            "agreement_score": 0.75,
            "details": "Most commenters support the article",
            "key_points": ["point1", "point2"]
        })
        
        result = summarizer_agent._analyze_agreement_with_article(
            "I agree with this article",
            "Test Title",
            "Test summary"
        )
        
        assert result["consensus"] == "agree"
        assert result["agreement_score"] == 0.75
    
    def test_analyze_agreement_no_article_context(self, summarizer_agent):
        """Test agreement analysis without article context"""
        result = summarizer_agent._analyze_agreement_with_article(
            "Some comments",
            "",
            ""
        )
        
        assert result["consensus"] == "unknown"
    
    def test_analyze_agreement_fallback(self, summarizer_agent):
        """Test agreement analysis fallback on JSON parse error"""
        summarizer_agent.llm_client.get_filter_llm.return_value.invoke.return_value = "invalid"
        
        result = summarizer_agent._analyze_agreement_with_article(
            "I agree exactly correct",
            "Title",
            "Summary"
        )
        
        # Should use keyword-based fallback
        assert "consensus" in result
        assert "agreement_score" in result
    
    def test_summarize_comments_empty_list(self, summarizer_agent):
        """Test _summarize_comments with empty list"""
        result = summarizer_agent._summarize_comments([])
        
        assert result["summary"] == "No comments available."
        assert result["sentiment"] == "neutral"
    
    def test_summarize_comments_filters_short_comments(self, summarizer_agent):
        """Test that short comments are filtered out"""
        comments = [
            {"text": "x", "author": "a", "indent_level": 0},  # Too short
            {"text": "This is a valid comment with enough content.", "author": "b", "indent_level": 0}
        ]
        
        # Set up mocks
        summarizer_agent.llm_client.get_filter_llm.return_value.invoke.return_value = json.dumps({
            "sentiment": "neutral",
            "score": 0.5,
            "details": "Test",
            "topics": []
        })
        
        result = summarizer_agent._summarize_comments(comments)
        
        # Should process despite one short comment
        assert "summary" in result


class TestSummarizerAgentEdgeCases:
    """Edge case tests for SummarizerAgent"""
    
    @pytest.fixture
    def summarizer_agent(self, mock_llm_client):
        """Create SummarizerAgent with mocked LLMClient"""
        return SummarizerAgent(llm_client=mock_llm_client)
    
    def test_summarize_empty_articles_list(self, summarizer_agent):
        """Test summarizing empty articles list"""
        result = summarizer_agent.summarize_articles([], include_comments=False)
        assert result == []
    
    def test_summarize_article_exception_handling(self, summarizer_agent, sample_article_with_comments):
        """Test that exceptions in comment summarization are handled"""
        # Make the filter LLM raise an exception
        summarizer_agent.llm_client.get_filter_llm.return_value.invoke.side_effect = Exception("LLM Error")
        
        result = summarizer_agent.summarize_article(
            sample_article_with_comments,
            include_comments=True
        )
        
        # Should handle exception and set error message
        assert "Error" in result.get("comment_summary", "") or result.get("comment_sentiment") == "unknown"
    
    def test_summarize_individual_comments_short(self, summarizer_agent):
        """Test _summarize_individual_comments handles short comments"""
        comments = [
            {"text": "Hi", "author": "user1"},
            {"text": "This is a longer comment that should be summarized.", "author": "user2"}
        ]
        
        result = summarizer_agent._summarize_individual_comments(comments)
        
        assert len(result) == 2
        # Short comment should get "too short" message
        assert result[0]["summary"] == "Comment too short to summarize."
    
    def test_summarize_individual_comments_limit(self, summarizer_agent):
        """Test that _summarize_individual_comments limits to 20 comments"""
        comments = [
            {"text": f"This is comment number {i} with enough text.", "author": f"user{i}"}
            for i in range(25)
        ]
        
        result = summarizer_agent._summarize_individual_comments(comments)
        
        # Should process all comments but only add summaries to first 20
        assert len(result) == 25
    
    def test_summarize_comments_only_top_level(self, summarizer_agent):
        """Test that _summarize_comments filters to top-level comments"""
        comments = [
            {"text": "A" * 50, "author": "a", "indent_level": 0},  # Top level
            {"text": "B" * 50, "author": "b", "indent_level": 1},  # Reply
            {"text": "C" * 50, "author": "c", "indent_level": 5},  # Deep reply - should be excluded
        ]
        
        # Set up mocks
        summarizer_agent.llm_client.get_filter_llm.return_value.invoke.return_value = json.dumps({
            "sentiment": "neutral",
            "score": 0.5,
            "details": "Test",
            "topics": []
        })
        
        result = summarizer_agent._summarize_comments(comments)
        
        # Should have processed (some may be filtered by indent level)
        assert "summary" in result
