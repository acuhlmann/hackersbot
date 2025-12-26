"""Formatters for console and file output"""

from typing import List, Dict, Any


class Formatter:
    """Formats summaries for different output types"""
    
    @staticmethod
    def format_console(articles: List[Dict]) -> str:
        """
        Format articles for console output.
        
        Args:
            articles: List of summarized articles
            
        Returns:
            Formatted string for console
        """
        lines = []
        lines.append("=" * 80)
        lines.append("HACKERNEWS SUMMARY")
        lines.append("=" * 80)
        lines.append("")
        
        for article in articles:
            rank = article.get("rank", "?")
            title = article.get("title", "Unknown")
            url = article.get("url", "")
            points = article.get("points", 0)
            author = article.get("author", "unknown")
            comment_count = article.get("comment_count", 0)
            
            lines.append(f"[{rank}] {title}")
            lines.append(f"    URL: {url}")
            lines.append(f"    Points: {points} | Author: {author} | Comments: {comment_count}")
            lines.append("")
            
            # Show AI classification if available
            if "ai_classification" in article:
                ai_info = article["ai_classification"]
                if ai_info.get("is_ai_related"):
                    lines.append(f"    🤖 AI-Related (confidence: {ai_info.get('confidence', 0):.2f})")
                    if ai_info.get("reasoning"):
                        lines.append(f"       {ai_info['reasoning']}")
                    lines.append("")
            
            # Show article summary
            if article.get("article_summary"):
                lines.append("    ARTICLE SUMMARY:")
                summary_lines = article["article_summary"].split("\n")
                for line in summary_lines:
                    lines.append(f"    {line}")
                lines.append("")
            
            # Skip individual comment summaries - focus on topic discussion
            
            # Show comment summary with sentiment
            if article.get("comment_summary"):
                lines.append("    OVERALL COMMENT SUMMARY:")
                summary_lines = article["comment_summary"].split("\n")
                for line in summary_lines:
                    lines.append(f"    {line}")
                lines.append("")
                
                # Show sentiment analysis
                sentiment = article.get("comment_sentiment")
                sentiment_score = article.get("comment_sentiment_score", 0.5)
                if sentiment:
                    sentiment_emoji = {
                        "positive": "😊",
                        "negative": "😞",
                        "neutral": "😐",
                        "mixed": "🤔"
                    }.get(sentiment, "😐")
                    lines.append(f"    SENTIMENT: {sentiment_emoji} {sentiment.upper()} (score: {sentiment_score:.2f})")
                    if article.get("comment_sentiment_details"):
                        lines.append(f"       {article['comment_sentiment_details']}")
                    lines.append("")
                
                # Show agreement/disagreement
                agreement = article.get("comment_agreement", {})
                if agreement and agreement.get("consensus") != "unknown":
                    consensus = agreement.get("consensus", "neutral")
                    agreement_score = agreement.get("agreement_score", 0.5)
                    consensus_emoji = {
                        "agree": "👍",
                        "disagree": "👎",
                        "mixed": "🤷",
                        "neutral": "😐"
                    }.get(consensus, "😐")
                    lines.append(f"    AGREEMENT: {consensus_emoji} {consensus.upper()} (score: {agreement_score:.2f})")
                    if agreement.get("details"):
                        lines.append(f"       {agreement['details']}")
                    lines.append("")
                
                # Show topics
                topics = article.get("comment_topics", [])
                if topics:
                    lines.append(f"    MAIN TOPICS: {', '.join(topics[:5])}")
                    lines.append("")
            
            lines.append("")
            lines.append("-" * 80)
            lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_markdown(articles: List[Dict], metadata: Dict[str, Any] = None) -> str:
        """
        Format articles as Markdown.
        
        Args:
            articles: List of summarized articles
            metadata: Optional metadata dictionary
            
        Returns:
            Markdown formatted string
        """
        lines = []
        lines.append("# HackerNews Summary")
        lines.append("")
        
        if metadata:
            lines.append("## Metadata")
            lines.append("")
            for key, value in metadata.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")
        
        lines.append("## Articles")
        lines.append("")
        
        for article in articles:
            rank = article.get("rank", "?")
            title = article.get("title", "Unknown")
            url = article.get("url", "")
            points = article.get("points", 0)
            author = article.get("author", "unknown")
            time_ago = article.get("time", "")
            comment_count = article.get("comment_count", 0)
            
            lines.append(f"### {rank}. {title}")
            lines.append("")
            lines.append(f"**URL:** [{url}]({url})")
            lines.append(f"**Points:** {points} | **Author:** {author} | **Time:** {time_ago} | **Comments:** {comment_count}")
            lines.append("")
            
            # Show AI classification if available
            if "ai_classification" in article:
                ai_info = article["ai_classification"]
                if ai_info.get("is_ai_related"):
                    confidence = ai_info.get("confidence", 0)
                    lines.append(f"**🤖 AI-Related** (confidence: {confidence:.2f})")
                    if ai_info.get("reasoning"):
                        lines.append(f"")
                        lines.append(f"*{ai_info['reasoning']}*")
                    lines.append("")
            
            # Article summary
            if article.get("article_summary"):
                lines.append("#### Article Summary")
                lines.append("")
                lines.append(article["article_summary"])
                lines.append("")
            
            # Skip individual comment summaries - focus on topic discussion
            
            # Comment summary with sentiment
            if article.get("comment_summary"):
                lines.append("#### Overall Comment Discussion Summary")
                lines.append("")
                lines.append(article["comment_summary"])
                lines.append("")
                
                # Sentiment analysis
                sentiment = article.get("comment_sentiment")
                sentiment_score = article.get("comment_sentiment_score", 0.5)
                if sentiment:
                    sentiment_emoji = {
                        "positive": "😊",
                        "negative": "😞",
                        "neutral": "😐",
                        "mixed": "🤔"
                    }.get(sentiment, "😐")
                    
                    lines.append("##### Comment Sentiment")
                    lines.append("")
                    lines.append(f"**Sentiment:** {sentiment_emoji} {sentiment.upper()} (score: {sentiment_score:.2f})")
                    lines.append("")
                    
                    if article.get("comment_sentiment_details"):
                        lines.append(f"*{article['comment_sentiment_details']}*")
                        lines.append("")
                
                # Agreement/disagreement with article
                agreement = article.get("comment_agreement", {})
                if agreement and agreement.get("consensus") != "unknown":
                    consensus = agreement.get("consensus", "neutral")
                    agreement_score = agreement.get("agreement_score", 0.5)
                    
                    consensus_emoji = {
                        "agree": "👍",
                        "disagree": "👎",
                        "mixed": "🤷",
                        "neutral": "😐"
                    }.get(consensus, "😐")
                    
                    lines.append("##### Agreement with Article")
                    lines.append("")
                    lines.append(f"**Consensus:** {consensus_emoji} {consensus.upper()} (score: {agreement_score:.2f})")
                    lines.append("")
                    
                    if agreement.get("details"):
                        lines.append(f"*{agreement['details']}*")
                        lines.append("")
                    
                    key_points = agreement.get("key_points", [])
                    if key_points:
                        lines.append("**Key Points:**")
                        lines.append("")
                        for point in key_points[:5]:
                            lines.append(f"- {point}")
                        lines.append("")
                
                # Topics being discussed
                topics = article.get("comment_topics", [])
                if topics:
                    lines.append("##### Main Discussion Topics")
                    lines.append("")
                    for topic in topics[:5]:
                        lines.append(f"- {topic}")
                    lines.append("")
            
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_json(articles: List[Dict], metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Format articles as JSON structure.
        
        Args:
            articles: List of summarized articles
            metadata: Optional metadata dictionary
            
        Returns:
            Dictionary ready for JSON serialization
        """
        return {
            "metadata": metadata or {},
            "articles": articles
        }

