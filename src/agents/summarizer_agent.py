"""Summarizer agent for generating article and comment summaries"""

import json
import logging
from typing import List, Dict, Optional
from src.models.llm_client import LLMClient, get_llm_client

logger = logging.getLogger(__name__)


class SummarizerAgent:
    """Generates summaries of articles and comments using LLM"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Initialize summarizer agent.
        
        Args:
            llm_client: Optional LLMClient instance (creates new one if not provided)
        """
        self.llm_client = llm_client or get_llm_client()
        self._current_article_title: Optional[str] = None
    
    def summarize_article(self, article: Dict, include_comments: bool = True) -> Dict:
        """
        Summarize an article and optionally its comments.
        
        Args:
            article: Article dictionary with title, url, content, and comments
            include_comments: Whether to include comment summaries
            
        Returns:
            Article dictionary with summary fields added
        """
        title = article.get("title", "")
        url = article.get("url", "")
        content = article.get("content", "")
        comments = article.get("comments", [])
        
        # Set current article title for event metadata
        self._current_article_title = title
        
        # Build article summary
        article_summary = self._summarize_article_content(title, url, content)
        article["article_summary"] = article_summary
        
        # Summarize comments if requested
        if include_comments and comments:
            try:
                logger.info("  Processing %d comments...", len(comments))
                # Skip individual summaries - focus on overall topic discussion
                # Just store comments as-is
                article["comments"] = comments
                
                # Get overall analysis of topics being discussed
                comment_analysis = self._summarize_comments(comments, article_title=title, article_summary=article_summary)
                article["comment_summary"] = comment_analysis.get("summary", "")
                article["comment_sentiment"] = comment_analysis.get("sentiment", "neutral")
                article["comment_sentiment_score"] = comment_analysis.get("sentiment_score", 0.5)
                article["comment_sentiment_details"] = comment_analysis.get("sentiment_details", "")
                article["comment_topics"] = comment_analysis.get("topics", [])
                article["comment_agreement"] = comment_analysis.get("agreement", {})
            except Exception as e:
                logger.warning("  ⚠️  Error summarizing comments: %s", e)
                article["comment_summary"] = f"Error summarizing comments: {str(e)}"
                article["comment_sentiment"] = "unknown"
                article["comment_sentiment_score"] = 0.5
                article["comment_sentiment_details"] = "Error occurred during sentiment analysis"
                article["comment_topics"] = []
        else:
            if not include_comments:
                logger.debug("  Skipping comments (include_comments=False)")
            elif not comments:
                logger.debug("  No comments found for this article")
            article["comment_summary"] = None
            article["comment_sentiment"] = None
            article["comment_sentiment_score"] = None
            article["comment_sentiment_details"] = None
            article["comment_topics"] = []
        
        return article
    
    def _summarize_article_content(self, title: str, url: str, content: Optional[str]) -> str:
        """Summarize article content"""
        if not content:
            # If no content available, create a summary based on title and URL
            summary_text = f"Title: {title}\nURL: {url}\n\nThis article was linked from Hacker News but the content could not be fetched."
        else:
            summary_text = f"Title: {title}\nURL: {url}\n\nContent:\n{content}"
        
        # Truncate if too long (to avoid token limits)
        max_chars = 3000
        if len(summary_text) > max_chars:
            summary_text = summary_text[:max_chars] + "..."
        
        logger.info("  Calling LLM to summarize article: %s", title[:50])
        summary = self.llm_client.summarize(summary_text, max_length=150, title=title, summarize_type="article")
        logger.info("  LLM summary generated (length: %d chars)", len(summary))
        return summary
    
    def _summarize_individual_comments(self, comments: List[Dict]) -> List[Dict]:
        """
        Add individual summaries to each comment (2-3 sentences each).
        
        Args:
            comments: List of comment dictionaries
            
        Returns:
            List of comments with 'summary' field added to each
        """
        if not comments:
            return []
        
        # Limit to top 20 comments to avoid too many LLM calls
        top_comments = comments[:20]
        comments_with_summaries = []
        
        for idx, comment in enumerate(top_comments, 1):
            comment_text = comment.get("text", "").strip()
            
            # Skip very short comments
            if len(comment_text) < 20:
                comment["summary"] = "Comment too short to summarize."
                comments_with_summaries.append(comment)
                continue
            
            try:
                # Summarize individual comment (limit to 500 chars)
                truncated_text = comment_text[:500]
                summary_prompt = f"""Summarize this comment in 2-3 sentences. Focus on the main point or opinion expressed.

Comment:
{truncated_text}

Summary:"""
                
                individual_summary = self.llm_client.get_summarizer_llm().invoke(summary_prompt).strip()
                comment["summary"] = individual_summary
                
                if idx % 5 == 0:
                    logger.info("    Summarized %d/%d comments...", idx, len(top_comments))
                    
            except Exception as e:
                # If summarization fails, use a truncated version
                comment["summary"] = comment_text[:150] + "..." if len(comment_text) > 150 else comment_text
            
            comments_with_summaries.append(comment)
        
        # Add remaining comments without summaries
        comments_with_summaries.extend(comments[20:])
        
        return comments_with_summaries
    
    def _summarize_comments(self, comments: List[Dict], article_title: str = "", article_summary: str = "") -> Dict[str, str]:
        """
        Summarize comment threads with sentiment analysis and agreement/disagreement with article.
        
        Args:
            comments: List of comment dictionaries
            article_title: Article title for agreement analysis
            article_summary: Article summary for agreement analysis
            
        Returns:
            Dictionary with 'summary', 'sentiment', 'topics', and 'agreement' keys
        """
        if not comments:
            return {
                "summary": "No comments available.",
                "sentiment": "neutral",
                "sentiment_score": 0.0,
                "topics": []
            }
        
        # Combine top-level comments (indent_level 0 or 1)
        # Limit to top 50 comments to get broader topic coverage
        top_comments = [c for c in comments if c.get("indent_level", 0) <= 1][:50]
        
        # Filter out comments without meaningful text
        valid_comments = [
            c for c in top_comments 
            if c.get('text') and len(c.get('text', '').strip()) >= 20
        ]
        
        if not valid_comments:
            logger.warning("  ⚠️  No valid comments found (all too short or empty)")
            return {
                "summary": "No substantial comments found to summarize.",
                "sentiment": "neutral",
                "sentiment_score": 0.5,
                "sentiment_details": "No comment content available for analysis",
                "topics": []
            }
        
        logger.info("  Using %d valid comments for summary", len(valid_comments))
        
        comments_text = "\n\n---\n\n".join([
            f"Comment by {c.get('author', 'unknown')}:\n{c.get('text', '')}"
            for c in valid_comments
        ])
        
        # Truncate if too long (increased limit for 50 comments)
        max_chars = 10000
        if len(comments_text) > max_chars:
            comments_text = comments_text[:max_chars] + "..."
            logger.debug("  ⚠️  Comment text truncated to %d chars", max_chars)
        
        # Get concise summary of what topics people are discussing (similar length to article summary)
        summary_prompt = f"""Summarize the main discussion topics from these Hacker News comments in a concise paragraph (around 100-150 words). 
Focus on the key themes and what people are discussing.

Comments:
{comments_text}

Concise summary of discussion topics:"""
        
        # Use the summarize method with max_length to keep it short like article summaries
        logger.info("  Calling LLM to summarize %d comments...", len(valid_comments))
        summary = self.llm_client.summarize(comments_text, max_length=150, title=article_title, summarize_type="comments")
        logger.info("  LLM comment summary generated (length: %d chars)", len(summary))
        
        # Get sentiment analysis
        sentiment_result = self._analyze_comment_sentiment(comments_text)
        
        # Get agreement/disagreement analysis with article
        agreement_result = self._analyze_agreement_with_article(
            comments_text, article_title, article_summary
        )
        
        return {
            "summary": summary,
            "sentiment": sentiment_result.get("sentiment", "neutral"),
            "sentiment_score": sentiment_result.get("score", 0.0),
            "sentiment_details": sentiment_result.get("details", ""),
            "topics": sentiment_result.get("topics", []),
            "agreement": agreement_result
        }
    
    def _analyze_comment_sentiment(self, comments_text: str) -> Dict:
        """Analyze sentiment of comments using LLM"""
        prompt = f"""Analyze the overall sentiment of these Hacker News comments. 
Consider the tone, opinions, and emotional content.

Comments:
{comments_text}

Respond with ONLY a JSON object in this exact format:
{{
    "sentiment": "positive/negative/neutral/mixed",
    "score": 0.0-1.0,
    "details": "brief explanation of the sentiment",
    "topics": ["topic1", "topic2", "topic3"]
}}

Where:
- sentiment: overall sentiment (positive, negative, neutral, or mixed)
- score: sentiment score from 0.0 (very negative) to 1.0 (very positive), with 0.5 being neutral
- details: brief explanation of why this sentiment was detected
- topics: list of main topics being discussed

JSON:"""
        
        try:
            logger.debug("  Calling LLM for sentiment analysis...")
            response = self.llm_client.get_filter_llm().invoke(prompt).strip()
            logger.debug("  LLM sentiment response received")
            
            # Extract JSON if wrapped in markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            result = json.loads(response)
            
            return {
                "sentiment": result.get("sentiment", "neutral").lower(),
                "score": float(result.get("score", 0.5)),
                "details": result.get("details", ""),
                "topics": result.get("topics", [])
            }
        except (json.JSONDecodeError, ValueError, KeyError, AttributeError) as e:
            # Fallback: simple keyword-based sentiment
            text_lower = comments_text.lower()
            positive_words = ["good", "great", "excellent", "love", "amazing", "thanks", "helpful", "useful"]
            negative_words = ["bad", "terrible", "hate", "awful", "wrong", "problem", "issue", "disappointed"]
            
            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)
            
            if positive_count > negative_count:
                sentiment = "positive"
                score = min(0.7, 0.5 + (positive_count - negative_count) * 0.1)
            elif negative_count > positive_count:
                sentiment = "negative"
                score = max(0.3, 0.5 - (negative_count - positive_count) * 0.1)
            else:
                sentiment = "neutral"
                score = 0.5
            
            return {
                "sentiment": sentiment,
                "score": score,
                "details": "Sentiment inferred from keywords (LLM parsing failed)",
                "topics": []
            }
    
    def _analyze_agreement_with_article(self, comments_text: str, article_title: str, article_summary: str) -> Dict:
        """
        Analyze whether commenters agree or disagree with the article.
        
        Args:
            comments_text: Combined text of comments
            article_title: Article title
            article_summary: Article summary
            
        Returns:
            Dictionary with agreement analysis
        """
        if not article_title and not article_summary:
            return {
                "consensus": "unknown",
                "agreement_score": 0.5,
                "details": "Article content not available for comparison"
            }
        
        article_context = f"Title: {article_title}\n\nSummary: {article_summary[:500]}"
        
        prompt = f"""Analyze whether the majority of commenters agree or disagree with the article's main points.

Article:
{article_context}

Comments:
{comments_text[:3000]}

Respond with ONLY a JSON object in this exact format:
{{
    "consensus": "agree/disagree/mixed/neutral",
    "agreement_score": 0.0-1.0,
    "details": "brief explanation of the consensus",
    "key_points": ["point1", "point2", "point3"]
}}

Where:
- consensus: Overall agreement (agree = majority support, disagree = majority critical, mixed = divided, neutral = no clear stance)
- agreement_score: 0.0 (strongly disagree) to 1.0 (strongly agree), 0.5 is neutral
- details: Brief explanation of why this consensus was determined
- key_points: List of main points commenters are agreeing/disagreeing about

JSON:"""
        
        try:
            logger.debug("  Calling LLM for agreement analysis...")
            response = self.llm_client.get_filter_llm().invoke(prompt).strip()
            logger.debug("  LLM agreement response received")
            
            # Extract JSON if wrapped in markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            result = json.loads(response)
            
            return {
                "consensus": result.get("consensus", "neutral").lower(),
                "agreement_score": float(result.get("agreement_score", 0.5)),
                "details": result.get("details", ""),
                "key_points": result.get("key_points", [])
            }
        except (json.JSONDecodeError, ValueError, KeyError, AttributeError) as e:
            # Fallback: simple keyword-based analysis
            text_lower = comments_text.lower()
            agree_words = ["agree", "correct", "right", "good point", "well said", "exactly", "true"]
            disagree_words = ["disagree", "wrong", "incorrect", "but", "however", "actually", "problem"]
            
            agree_count = sum(1 for word in agree_words if word in text_lower)
            disagree_count = sum(1 for word in disagree_words if word in text_lower)
            
            if agree_count > disagree_count * 1.5:
                consensus = "agree"
                score = min(0.8, 0.5 + (agree_count - disagree_count) * 0.05)
            elif disagree_count > agree_count * 1.5:
                consensus = "disagree"
                score = max(0.2, 0.5 - (disagree_count - agree_count) * 0.05)
            else:
                consensus = "mixed"
                score = 0.5
            
            return {
                "consensus": consensus,
                "agreement_score": score,
                "details": "Agreement inferred from keywords (LLM parsing failed)",
                "key_points": []
            }
    
    def summarize_articles(self, articles: List[Dict], include_comments: bool = True) -> List[Dict]:
        """
        Summarize multiple articles.
        
        Args:
            articles: List of article dictionaries
            include_comments: Whether to include comment summaries
            
        Returns:
            List of articles with summary fields added
        """
        summarized = []
        
        for idx, article in enumerate(articles, 1):
            logger.info("Summarizing article %d/%d: %s...", idx, len(articles), article.get('title', 'Unknown')[:50])
            summarized_article = self.summarize_article(article, include_comments=include_comments)
            summarized.append(summarized_article)
        
        return summarized

