"""Telegram bot for HackerNews AI Summarizer"""

import os
import logging
import asyncio
from typing import Optional
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.agents.scraper_agent import ScraperAgent
from src.agents.filter_agent import FilterAgent
from src.agents.summarizer_agent import SummarizerAgent
from src.models.llm_client import get_llm_client

load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Default settings
DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")
DEFAULT_TOP_N = 3


class HNSummaryBot:
    """Telegram bot that provides Hacker News summaries"""
    
    def __init__(self, token: Optional[str] = None, provider: Optional[str] = None):
        """
        Initialize the bot.
        
        Args:
            token: Telegram bot token (default: from TELEGRAM_BOT_TOKEN env var)
            provider: LLM provider (default: from LLM_PROVIDER env var or 'deepseek')
        """
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError(
                "Telegram bot token is required. Set TELEGRAM_BOT_TOKEN environment variable."
            )
        
        self.provider = provider or DEFAULT_PROVIDER
        self.llm_client = get_llm_client(provider=self.provider)
        
        # Initialize agents
        self.scraper = ScraperAgent()
        self.filter_agent = FilterAgent(llm_client=self.llm_client)
        self.summarizer = SummarizerAgent(llm_client=self.llm_client)
        
        logger.info(f"Bot initialized with LLM provider: {self.provider}")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        welcome_message = """👋 Welcome to HackerNews AI Summarizer Bot!

I can fetch and summarize the top articles from Hacker News for you.

**Available Commands:**
/summary - Get top 3 HN articles summarized
/summary N - Get top N articles (e.g., /summary 5)
/ai - Get AI-related articles only
/ai N - Get top N AI-related articles
/help - Show this help message

🤖 Currently using: {provider} for AI summaries

Just send a command to get started!
""".format(provider=self.provider.upper())
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        help_text = """📖 **HackerNews Summarizer Bot Help**

**Commands:**
• `/summary` - Summarize top 3 articles
• `/summary 5` - Summarize top 5 articles
• `/ai` - Get AI-related articles (top 10 scanned)
• `/ai 20` - Scan top 20 for AI articles
• `/help` - Show this message

**Tips:**
• Summaries include article content and comment discussions
• AI filtering scans more articles to find relevant ones
• Each summary takes ~10-30 seconds depending on article count

🤖 Provider: {provider}
""".format(provider=self.provider.upper())
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def summary_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /summary command"""
        # Parse number of articles from args
        top_n = DEFAULT_TOP_N
        if context.args:
            try:
                top_n = int(context.args[0])
                top_n = max(1, min(top_n, 10))  # Limit to 1-10
            except ValueError:
                await update.message.reply_text("⚠️ Invalid number. Using default (3).")
        
        await self._fetch_and_summarize(update, top_n, filter_ai=False)
    
    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /ai command - get AI-related articles"""
        # Parse number of articles to scan
        scan_n = 10
        if context.args:
            try:
                scan_n = int(context.args[0])
                scan_n = max(5, min(scan_n, 30))  # Limit to 5-30
            except ValueError:
                await update.message.reply_text("⚠️ Invalid number. Scanning top 10.")
        
        await self._fetch_and_summarize(update, scan_n, filter_ai=True)
    
    async def _fetch_and_summarize(
        self, 
        update: Update, 
        top_n: int, 
        filter_ai: bool = False
    ) -> None:
        """Fetch articles and send summaries"""
        # Send initial status
        if filter_ai:
            status_msg = await update.message.reply_text(
                f"🔍 Scanning top {top_n} articles for AI-related content...\n"
                f"This may take a minute..."
            )
        else:
            status_msg = await update.message.reply_text(
                f"📰 Fetching top {top_n} articles from Hacker News...\n"
                f"This may take a minute..."
            )
        
        try:
            # Step 1: Scrape articles
            articles = self.scraper.scrape_articles_with_comments(top_n)
            
            if not articles:
                await status_msg.edit_text("❌ No articles found. Please try again later.")
                return
            
            await status_msg.edit_text(
                f"✅ Found {len(articles)} articles\n"
                f"🤖 Analyzing with {self.provider.upper()}..."
            )
            
            # Step 2: Filter if requested
            if filter_ai:
                articles = self.filter_agent.filter_ai_articles(articles, min_confidence=0.5)
                if not articles:
                    await status_msg.edit_text(
                        "❌ No AI-related articles found in the top stories.\n"
                        "Try scanning more articles with `/ai 20`"
                    )
                    return
                await status_msg.edit_text(
                    f"✅ Found {len(articles)} AI-related articles\n"
                    f"📝 Generating summaries..."
                )
            else:
                # Still classify for metadata
                articles = self.filter_agent.batch_classify(articles)
                await status_msg.edit_text(
                    f"✅ Classified {len(articles)} articles\n"
                    f"📝 Generating summaries..."
                )
            
            # Step 3: Summarize
            articles = self.summarizer.summarize_articles(articles, include_comments=True)
            
            # Step 4: Format and send results
            await status_msg.edit_text("✅ Summaries ready! Sending...")
            
            # Send each article as a separate message
            for i, article in enumerate(articles, 1):
                message = self._format_article_message(article, i, len(articles))
                
                # Telegram has a 4096 character limit per message
                if len(message) > 4000:
                    message = message[:3997] + "..."
                
                await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)
            
            # Final status
            await status_msg.edit_text(
                f"✨ Done! Sent {len(articles)} article summaries.\n"
                f"Use /summary or /ai for more!"
            )
            
        except Exception as e:
            logger.error(f"Error in fetch_and_summarize: {e}", exc_info=True)
            await status_msg.edit_text(
                f"❌ Error occurred: {str(e)[:100]}\n"
                f"Please try again later."
            )
    
    def _format_article_message(self, article: dict, index: int, total: int) -> str:
        """Format an article as a Telegram message"""
        title = article.get("title", "Untitled")
        url = article.get("url", "")
        points = article.get("points", 0)
        comments_count = article.get("comments_count", 0)
        article_summary = article.get("article_summary", "No summary available.")
        comment_summary = article.get("comment_summary", "")
        
        # AI classification info
        ai_info = ""
        if article.get("ai_classification", {}).get("is_ai_related"):
            confidence = article["ai_classification"].get("confidence", 0)
            ai_info = f"🤖 AI-Related ({confidence:.0%})\n"
        
        # Comment sentiment
        sentiment_info = ""
        sentiment = article.get("comment_sentiment")
        if sentiment:
            sentiment_emoji = {
                "positive": "😊",
                "negative": "😟", 
                "neutral": "😐",
                "mixed": "🤔"
            }.get(sentiment, "")
            sentiment_info = f"💬 Sentiment: {sentiment_emoji} {sentiment.title()}\n"
        
        message = f"""📰 **[{index}/{total}] {title}**

{ai_info}⬆️ {points} points | 💬 {comments_count} comments
🔗 {url}

**Summary:**
{article_summary}
"""
        
        if comment_summary:
            message += f"""
**Discussion Highlights:**
{comment_summary}
"""
        
        if sentiment_info:
            message += f"\n{sentiment_info}"
        
        return message
    
    def run(self) -> None:
        """Run the bot (blocking)"""
        logger.info("Starting Telegram bot...")
        
        # Create application
        application = Application.builder().token(self.token).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("summary", self.summary_command))
        application.add_handler(CommandHandler("ai", self.ai_command))
        
        # Start polling
        logger.info("Bot is running. Press Ctrl+C to stop.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Entry point for the Telegram bot"""
    import argparse
    
    parser = argparse.ArgumentParser(description="HackerNews AI Summarizer Telegram Bot")
    parser.add_argument(
        "--provider",
        choices=["ollama", "deepseek"],
        default=os.getenv("LLM_PROVIDER", "deepseek"),
        help="LLM provider (default: deepseek)"
    )
    args = parser.parse_args()
    
    try:
        bot = HNSummaryBot(provider=args.provider)
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise


if __name__ == "__main__":
    main()
