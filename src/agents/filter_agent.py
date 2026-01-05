"""Filter agent for identifying AI-related topics"""

from typing import List, Dict, Optional, Any, Union
from src.models.llm_client import LLMClient, get_llm_client

# Type alias for article dictionaries
Article = Dict[str, Any]
Classification = Dict[str, Any]


class FilterAgent:
    """Filters articles to identify AI-related topics"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Initialize filter agent.
        
        Args:
            llm_client: Optional LLMClient instance (creates new one if not provided)
        """
        self.llm_client = llm_client or get_llm_client()
    
    def filter_ai_articles(self, articles: List[Dict], min_confidence: float = 0.5) -> List[Dict]:
        """
        Filter articles to only include AI-related ones.
        
        Args:
            articles: List of article dictionaries
            min_confidence: Minimum confidence threshold (0.0-1.0)
            
        Returns:
            Filtered list of articles with AI classification metadata
        """
        filtered = []
        
        for article in articles:
            classification = self.classify_article(article)
            article["ai_classification"] = classification
            
            if classification["is_ai_related"] and classification["confidence"] >= min_confidence:
                filtered.append(article)
        
        return filtered
    
    def classify_article(self, article: Dict) -> Dict:
        """
        Classify a single article as AI-related or not.
        
        Args:
            article: Article dictionary with title, url, and optionally content
            
        Returns:
            Classification dictionary with is_ai_related, confidence, and reasoning
        """
        title = article.get("title", "")
        url = article.get("url", "")
        content = article.get("content", "")
        
        # Use LLM client to classify
        classification = self.llm_client.classify_ai_topic(
            title=title,
            url=url,
            content=content
        )
        
        return classification
    
    def batch_classify(self, articles: List[Dict]) -> List[Dict]:
        """
        Classify multiple articles and add classification metadata to each.
        
        Args:
            articles: List of article dictionaries
            
        Returns:
            List of articles with ai_classification metadata added
        """
        for article in articles:
            if "ai_classification" not in article:
                article["ai_classification"] = self.classify_article(article)
        
        return articles

