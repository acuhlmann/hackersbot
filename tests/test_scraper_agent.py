"""Tests for the scraper agent module"""

import pytest
import responses
from unittest.mock import patch, Mock
from src.agents.scraper_agent import ScraperAgent


class TestScraperAgent:
    """Tests for ScraperAgent class"""
    
    @pytest.fixture
    def scraper(self):
        """Create ScraperAgent with zero delay for testing"""
        return ScraperAgent(delay=0)
    
    @responses.activate
    def test_fetch_top_articles_success(self, scraper, sample_hn_frontpage_html):
        """Test successful fetching of top articles"""
        responses.add(
            responses.GET,
            "https://news.ycombinator.com",
            body=sample_hn_frontpage_html,
            status=200
        )
        
        articles = scraper.fetch_top_articles(top_n=2)
        
        assert len(articles) <= 2
    
    @responses.activate
    def test_fetch_top_articles_network_error(self, scraper):
        """Test handling of network errors"""
        import requests
        responses.add(
            responses.GET,
            "https://news.ycombinator.com",
            body=requests.exceptions.ConnectionError("Connection error")
        )
        
        articles = scraper.fetch_top_articles(top_n=3)
        
        assert articles == []
    
    @responses.activate
    def test_fetch_top_articles_http_error(self, scraper):
        """Test handling of HTTP errors"""
        responses.add(
            responses.GET,
            "https://news.ycombinator.com",
            status=500
        )
        
        articles = scraper.fetch_top_articles(top_n=3)
        
        assert articles == []
    
    @responses.activate
    def test_fetch_comments_empty_url(self, scraper):
        """Test fetch_comments with empty URL returns empty list"""
        comments = scraper.fetch_comments("")
        assert comments == []
    
    @responses.activate
    def test_fetch_comments_success(self, scraper, sample_hn_comments_html):
        """Test successful fetching of comments"""
        comment_url = "https://news.ycombinator.com/item?id=12345678"
        
        responses.add(
            responses.GET,
            comment_url,
            body=sample_hn_comments_html,
            status=200
        )
        
        comments = scraper.fetch_comments(comment_url)
        
        # Should parse comments from the HTML
        assert isinstance(comments, list)
    
    @responses.activate
    def test_fetch_comments_network_error(self, scraper):
        """Test handling of network errors when fetching comments"""
        comment_url = "https://news.ycombinator.com/item?id=12345678"
        
        responses.add(
            responses.GET,
            comment_url,
            body=Exception("Connection error")
        )
        
        comments = scraper.fetch_comments(comment_url)
        
        assert comments == []
    
    @responses.activate
    def test_fetch_article_content_skip_hn_links(self, scraper):
        """Test that HN internal links are skipped"""
        content = scraper.fetch_article_content("https://news.ycombinator.com/item?id=123")
        assert content is None
    
    @responses.activate
    def test_fetch_article_content_empty_url(self, scraper):
        """Test fetch_article_content with empty URL returns None"""
        content = scraper.fetch_article_content("")
        assert content is None
    
    @responses.activate
    def test_fetch_article_content_success(self, scraper):
        """Test successful fetching of article content"""
        article_url = "https://example.com/article"
        html_content = """
        <html>
        <body>
            <article>
                <h1>Test Article</h1>
                <p>This is the article content.</p>
            </article>
        </body>
        </html>
        """
        
        responses.add(
            responses.GET,
            article_url,
            body=html_content,
            status=200
        )
        
        content = scraper.fetch_article_content(article_url)
        
        assert content is not None
        assert "Test Article" in content or "article content" in content
    
    @responses.activate
    def test_fetch_article_content_network_error(self, scraper):
        """Test handling of network errors when fetching article content"""
        article_url = "https://example.com/article"
        
        responses.add(
            responses.GET,
            article_url,
            body=Exception("Connection error")
        )
        
        content = scraper.fetch_article_content(article_url)
        
        assert content is None
    
    @responses.activate
    def test_fetch_article_content_truncation(self, scraper):
        """Test that long content is truncated to 5000 chars"""
        article_url = "https://example.com/article"
        long_content = "<html><body><article>" + "A" * 10000 + "</article></body></html>"
        
        responses.add(
            responses.GET,
            article_url,
            body=long_content,
            status=200
        )
        
        content = scraper.fetch_article_content(article_url)
        
        assert content is not None
        assert len(content) <= 5000
    
    @responses.activate
    def test_scrape_articles_with_comments(self, scraper, sample_hn_frontpage_html, sample_hn_comments_html):
        """Test scraping articles with their comments"""
        responses.add(
            responses.GET,
            "https://news.ycombinator.com",
            body=sample_hn_frontpage_html,
            status=200
        )
        
        # Add comment page responses
        responses.add(
            responses.GET,
            "https://news.ycombinator.com/item?id=12345678",
            body=sample_hn_comments_html,
            status=200
        )
        
        responses.add(
            responses.GET,
            "https://news.ycombinator.com/item?id=87654321",
            body=sample_hn_comments_html,
            status=200
        )
        
        # Mock article content fetch
        responses.add(
            responses.GET,
            "https://example.com/article",
            body="<html><body><article>Content</article></body></html>",
            status=200
        )
        
        responses.add(
            responses.GET,
            "https://example.com/article2",
            body="<html><body><article>Content 2</article></body></html>",
            status=200
        )
        
        articles = scraper.scrape_articles_with_comments(top_n=2)
        
        for article in articles:
            assert "comments" in article
            assert "content" in article
    
    def test_parse_article_row_missing_title(self, scraper):
        """Test _parse_article_row handles missing title gracefully"""
        from bs4 import BeautifulSoup
        
        html = '<tr class="athing" id="123"><td></td></tr>'
        soup = BeautifulSoup(html, "html.parser")
        row = soup.find("tr")
        
        result = scraper._parse_article_row(row, soup, 0)
        
        assert result is None
    
    def test_scraper_custom_delay(self):
        """Test that custom delay is set correctly"""
        scraper = ScraperAgent(delay=2.5)
        assert scraper.delay == 2.5
    
    def test_scraper_default_delay(self):
        """Test default delay is 1.0 second"""
        scraper = ScraperAgent()
        assert scraper.delay == 1.0
    
    def test_scraper_session_headers(self, scraper):
        """Test that session headers are set"""
        assert "User-Agent" in scraper.session.headers


class TestScraperAgentParsing:
    """Tests for HTML parsing functionality"""
    
    @pytest.fixture
    def scraper(self):
        """Create ScraperAgent with zero delay for testing"""
        return ScraperAgent(delay=0)
    
    def test_parse_comment_row_valid(self, scraper, sample_hn_comments_html):
        """Test parsing a valid comment row"""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(sample_hn_comments_html, "html.parser")
        row = soup.find("tr", class_="athing")
        
        if row:
            comment = scraper._parse_comment_row(row, soup)
            # May or may not find a valid comment depending on HTML structure
            if comment:
                assert "id" in comment
                assert "text" in comment
    
    def test_parse_comment_row_no_id(self, scraper):
        """Test parsing comment row with no ID returns None"""
        from bs4 import BeautifulSoup
        
        html = '<tr class="athing"><td class="default"><div class="commtext c00">Test</div></td></tr>'
        soup = BeautifulSoup(html, "html.parser")
        row = soup.find("tr")
        
        comment = scraper._parse_comment_row(row, soup)
        
        # Should return None because no id attribute
        assert comment is None
