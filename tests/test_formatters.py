"""Tests for the formatters module"""

import pytest
from src.utils.formatters import Formatter


class TestFormatterConsole:
    """Tests for console formatting"""
    
    def test_format_console_empty_articles(self):
        """Test console formatting with empty article list"""
        result = Formatter.format_console([])
        assert "HACKERNEWS SUMMARY" in result
        assert "=" * 80 in result
    
    def test_format_console_basic_article(self, sample_article):
        """Test console formatting with basic article"""
        result = Formatter.format_console([sample_article])
        
        assert "[1]" in result
        assert sample_article["title"] in result
        assert sample_article["url"] in result
        assert f"Points: {sample_article['points']}" in result
        assert f"Author: {sample_article['author']}" in result
    
    def test_format_console_with_summary(self, sample_summarized_article):
        """Test console formatting with fully summarized article"""
        result = Formatter.format_console([sample_summarized_article])
        
        assert "ARTICLE SUMMARY:" in result
        assert sample_summarized_article["article_summary"] in result
        assert "OVERALL COMMENT SUMMARY:" in result
        assert "SENTIMENT:" in result
    
    def test_format_console_ai_classification(self, sample_summarized_article):
        """Test console formatting shows AI classification"""
        result = Formatter.format_console([sample_summarized_article])
        
        assert "🤖 AI-Related" in result
        assert "confidence:" in result
    
    def test_format_console_multiple_articles(self, sample_article):
        """Test console formatting with multiple articles"""
        article1 = sample_article.copy()
        article1["rank"] = 1
        article1["title"] = "First Article"
        
        article2 = sample_article.copy()
        article2["rank"] = 2
        article2["title"] = "Second Article"
        
        result = Formatter.format_console([article1, article2])
        
        assert "[1]" in result
        assert "[2]" in result
        assert "First Article" in result
        assert "Second Article" in result
    
    def test_format_console_sentiment_emojis(self, sample_summarized_article):
        """Test that sentiment emojis are correctly displayed"""
        # Test positive sentiment
        article = sample_summarized_article.copy()
        article["comment_sentiment"] = "positive"
        result = Formatter.format_console([article])
        assert "😊" in result
        
        # Test negative sentiment
        article["comment_sentiment"] = "negative"
        result = Formatter.format_console([article])
        assert "😞" in result
        
        # Test mixed sentiment
        article["comment_sentiment"] = "mixed"
        result = Formatter.format_console([article])
        assert "🤔" in result


class TestFormatterMarkdown:
    """Tests for markdown formatting"""
    
    def test_format_markdown_empty_articles(self):
        """Test markdown formatting with empty article list"""
        result = Formatter.format_markdown([])
        assert "# HackerNews Summary" in result
        assert "## Articles" in result
    
    def test_format_markdown_basic_article(self, sample_article):
        """Test markdown formatting with basic article"""
        result = Formatter.format_markdown([sample_article])
        
        assert f"### 1. {sample_article['title']}" in result
        assert f"**URL:** [{sample_article['url']}]" in result
        assert f"**Points:** {sample_article['points']}" in result
    
    def test_format_markdown_with_metadata(self, sample_article):
        """Test markdown formatting includes metadata"""
        metadata = {
            "top_n": 10,
            "filter_ai": True,
            "articles_count": 5
        }
        result = Formatter.format_markdown([sample_article], metadata)
        
        assert "## Metadata" in result
        assert "**top_n**: 10" in result
        assert "**filter_ai**: True" in result
    
    def test_format_markdown_with_summary(self, sample_summarized_article):
        """Test markdown formatting with summarized article"""
        result = Formatter.format_markdown([sample_summarized_article])
        
        assert "#### Article Summary" in result
        assert sample_summarized_article["article_summary"] in result
        assert "#### Overall Comment Discussion Summary" in result
    
    def test_format_markdown_agreement_section(self, sample_summarized_article):
        """Test markdown formatting includes agreement section"""
        result = Formatter.format_markdown([sample_summarized_article])
        
        assert "##### Agreement with Article" in result
        assert "**Consensus:**" in result
    
    def test_format_markdown_topics(self, sample_summarized_article):
        """Test markdown formatting includes discussion topics"""
        result = Formatter.format_markdown([sample_summarized_article])
        
        assert "##### Main Discussion Topics" in result
        for topic in sample_summarized_article["comment_topics"][:5]:
            assert f"- {topic}" in result


class TestFormatterJSON:
    """Tests for JSON formatting"""
    
    def test_format_json_empty_articles(self):
        """Test JSON formatting with empty article list"""
        result = Formatter.format_json([])
        
        assert "metadata" in result
        assert "articles" in result
        assert result["articles"] == []
    
    def test_format_json_with_articles(self, sample_article):
        """Test JSON formatting preserves article data"""
        result = Formatter.format_json([sample_article])
        
        assert len(result["articles"]) == 1
        assert result["articles"][0]["title"] == sample_article["title"]
        assert result["articles"][0]["url"] == sample_article["url"]
    
    def test_format_json_with_metadata(self, sample_article):
        """Test JSON formatting includes metadata"""
        metadata = {"top_n": 10, "filter_ai": True}
        result = Formatter.format_json([sample_article], metadata)
        
        assert result["metadata"]["top_n"] == 10
        assert result["metadata"]["filter_ai"] is True
    
    def test_format_json_none_metadata(self, sample_article):
        """Test JSON formatting handles None metadata"""
        result = Formatter.format_json([sample_article], None)
        
        assert result["metadata"] == {}
    
    def test_format_json_multiple_articles(self, sample_article):
        """Test JSON formatting with multiple articles"""
        articles = [sample_article.copy() for _ in range(3)]
        result = Formatter.format_json(articles)
        
        assert len(result["articles"]) == 3
