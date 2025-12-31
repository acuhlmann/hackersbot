"""Pytest fixtures and shared test configuration"""

import pytest
from unittest.mock import Mock, MagicMock


@pytest.fixture
def sample_article():
    """Sample article data for testing"""
    return {
        "id": "12345678",
        "rank": 1,
        "title": "OpenAI Releases New GPT Model",
        "url": "https://example.com/article",
        "points": 250,
        "author": "testuser",
        "time": "2024-01-15 10:30:00",
        "comment_count": 42,
        "comment_url": "https://news.ycombinator.com/item?id=12345678"
    }


@pytest.fixture
def sample_article_with_content(sample_article):
    """Sample article with content for testing"""
    article = sample_article.copy()
    article["content"] = "This is the article content about AI and machine learning."
    return article


@pytest.fixture
def sample_comments():
    """Sample comments data for testing"""
    return [
        {
            "id": "11111111",
            "author": "commenter1",
            "text": "This is a great article about AI developments. I think it's really important.",
            "time": "2024-01-15 11:00:00",
            "indent_level": 0
        },
        {
            "id": "22222222",
            "author": "commenter2",
            "text": "I disagree with some points here. The technology isn't as advanced as claimed.",
            "time": "2024-01-15 11:30:00",
            "indent_level": 1
        },
        {
            "id": "33333333",
            "author": "commenter3",
            "text": "Interesting perspective. We need to consider the implications carefully.",
            "time": "2024-01-15 12:00:00",
            "indent_level": 0
        }
    ]


@pytest.fixture
def sample_article_with_comments(sample_article_with_content, sample_comments):
    """Sample article with comments for testing"""
    article = sample_article_with_content.copy()
    article["comments"] = sample_comments
    return article


@pytest.fixture
def sample_summarized_article(sample_article_with_comments):
    """Sample fully summarized article for testing"""
    article = sample_article_with_comments.copy()
    article["article_summary"] = "This article discusses new AI developments and their implications."
    article["comment_summary"] = "Commenters have mixed opinions on the article."
    article["comment_sentiment"] = "mixed"
    article["comment_sentiment_score"] = 0.5
    article["comment_sentiment_details"] = "The discussion is balanced with both positive and critical views."
    article["comment_topics"] = ["AI development", "technology advancement", "implications"]
    article["comment_agreement"] = {
        "consensus": "mixed",
        "agreement_score": 0.5,
        "details": "Some agree while others disagree",
        "key_points": ["AI capabilities", "timeline predictions"]
    }
    article["ai_classification"] = {
        "is_ai_related": True,
        "confidence": 0.95,
        "reasoning": "Article discusses OpenAI and GPT models"
    }
    return article


@pytest.fixture
def mock_ollama_client():
    """Mock OllamaClient for testing agents"""
    mock_client = Mock()
    
    # Mock summarize method
    mock_client.summarize.return_value = "This is a test summary."
    
    # Mock classify_ai_topic method
    mock_client.classify_ai_topic.return_value = {
        "is_ai_related": True,
        "confidence": 0.9,
        "reasoning": "Content is about AI"
    }
    
    # Mock get_summarizer_llm
    mock_summarizer_llm = Mock()
    mock_summarizer_llm.invoke.return_value = "Test summary response"
    mock_client.get_summarizer_llm.return_value = mock_summarizer_llm
    
    # Mock get_filter_llm
    mock_filter_llm = Mock()
    mock_filter_llm.invoke.return_value = '{"sentiment": "positive", "score": 0.8, "details": "Test details", "topics": ["AI", "tech"]}'
    mock_client.get_filter_llm.return_value = mock_filter_llm
    
    return mock_client


@pytest.fixture
def sample_hn_frontpage_html():
    """Sample Hacker News front page HTML for testing scraper"""
    return """
    <html>
    <body>
    <table>
        <tr class="athing" id="12345678">
            <td class="title">
                <span class="titleline">
                    <a href="https://example.com/article">Test Article Title</a>
                </span>
            </td>
        </tr>
        <tr>
            <td class="subtext">
                <span class="score" id="score_12345678">150 points</span>
                by <a class="hnuser">testuser</a>
                <span class="age" title="2024-01-15">5 hours ago</span>
                |
                <a href="item?id=12345678">42 comments</a>
            </td>
        </tr>
        <tr class="athing" id="87654321">
            <td class="title">
                <span class="titleline">
                    <a href="https://example.com/article2">Second Article</a>
                </span>
            </td>
        </tr>
        <tr>
            <td class="subtext">
                <span class="score" id="score_87654321">75 points</span>
                by <a class="hnuser">anotheruser</a>
                <span class="age" title="2024-01-15">3 hours ago</span>
                |
                <a href="item?id=87654321">20 comments</a>
            </td>
        </tr>
    </table>
    </body>
    </html>
    """


@pytest.fixture
def sample_hn_comments_html():
    """Sample Hacker News comments page HTML for testing"""
    return """
    <html>
    <body>
    <table>
        <tr class="athing" id="11111111">
            <td class="ind"><img width="0"></td>
            <td class="default">
                <div class="commtext c00">
                    This is a test comment with enough text to be considered valid.
                    It discusses the main points of the article.
                </div>
            </td>
        </tr>
        <tr>
            <td></td>
            <td class="default">
                <a class="hnuser">commenter1</a>
                <span class="age" title="2024-01-15">2 hours ago</span>
            </td>
        </tr>
        <tr class="athing" id="22222222">
            <td class="ind"><img width="40"></td>
            <td class="default">
                <div class="commtext c00">
                    A reply comment that is also substantial and contains meaningful discussion.
                </div>
            </td>
        </tr>
        <tr>
            <td></td>
            <td class="default">
                <a class="hnuser">commenter2</a>
                <span class="age" title="2024-01-15">1 hour ago</span>
            </td>
        </tr>
    </table>
    </body>
    </html>
    """
