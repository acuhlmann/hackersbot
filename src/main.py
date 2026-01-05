"""Main CLI interface for HackerNews AI Summarizer"""

import logging
import click
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables from .env file (not .env.example - that's just a template)
# In production (GitHub Actions, GCP VM), environment variables are injected directly
# so .env file won't exist and load_dotenv() will silently continue
try:
    # Find project root (go up from src/ to project root)
    project_root = Path(__file__).parent.parent.resolve()
    load_dotenv(dotenv_path=str(project_root / '.env'))  # Explicitly load from project root
except Exception as e:
    # If .env file has encoding issues, log warning but continue
    # Production environments use injected env vars, so this is fine
    print(f"Warning: Could not load .env file: {e}. Continuing with environment variables.", flush=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
from src.agents.scraper_agent import ScraperAgent
from src.agents.filter_agent import FilterAgent
from src.agents.summarizer_agent import SummarizerAgent
from src.utils.storage import Storage
from src.utils.formatters import Formatter
from src.models.llm_client import get_llm_client


@click.command()
@click.option(
    "--top-n",
    default=3,
    type=int,
    help="Number of top articles to scrape and summarize (default: 3)"
)
@click.option(
    "--output-format",
    type=click.Choice(["console", "file", "both"], case_sensitive=False),
    default="both",
    help="Output format: console, file, or both (default: both)"
)
@click.option(
    "--filter-ai",
    is_flag=True,
    help="Filter to only AI-related articles (useful with --top-n 30)"
)
@click.option(
    "--min-confidence",
    default=0.5,
    type=float,
    help="Minimum confidence threshold for AI filtering (0.0-1.0, default: 0.5)"
)
@click.option(
    "--no-comments",
    is_flag=True,
    help="Skip comment summarization (faster)"
)
def main(top_n: int, output_format: str, filter_ai: bool, min_confidence: float, no_comments: bool):
    """
    HackerNews AI Summarizer - Scrape and summarize top articles from Hacker News.
    
    Example usage:
    
        python -m src.main --top-n 3
    
        python -m src.main --top-n 30 --filter-ai
    """
    click.echo("🚀 Starting HackerNews AI Summarizer...")
    click.echo(f"📊 Fetching top {top_n} articles...")
    
    # Initialize shared LLM client (uses DeepSeek)
    llm_client = get_llm_client()
    click.echo("🤖 Using DeepSeek LLM")
    
    # Initialize agents with shared LLM client
    scraper = ScraperAgent()
    filter_agent = FilterAgent(llm_client=llm_client)
    summarizer = SummarizerAgent(llm_client=llm_client)
    storage = Storage()
    
    # Step 1: Scrape articles
    articles = scraper.scrape_articles_with_comments(top_n)
    
    if not articles:
        click.echo("❌ No articles found. Exiting.")
        return
    
    click.echo(f"✅ Scraped {len(articles)} articles")
    
    # Step 2: Filter AI articles if requested
    if filter_ai:
        click.echo("🔍 Filtering AI-related articles...")
        articles = filter_agent.filter_ai_articles(articles, min_confidence=min_confidence)
        click.echo(f"✅ Found {len(articles)} AI-related articles")
        
        if not articles:
            click.echo("❌ No AI-related articles found. Exiting.")
            return
    else:
        # Still classify for metadata, but don't filter
        click.echo("🔍 Classifying articles...")
        articles = filter_agent.batch_classify(articles)
    
    # Step 3: Summarize articles
    click.echo("📝 Summarizing articles...")
    articles = summarizer.summarize_articles(articles, include_comments=not no_comments)
    click.echo("✅ Summarization complete")
    
    # Step 4: Output results
    metadata = {
        "top_n": top_n,
        "filter_ai": filter_ai,
        "min_confidence": min_confidence if filter_ai else None,
        "include_comments": not no_comments,
        "articles_count": len(articles),
        "llm_provider": "deepseek"
    }
    
    if output_format in ["console", "both"]:
        click.echo("\n" + "=" * 80)
        console_output = Formatter.format_console(articles)
        click.echo(console_output)
    
    if output_format in ["file", "both"]:
        click.echo("\n💾 Saving to files...")
        
        # Use date-only filenames to keep one summary per day
        # (running multiple times in a day will replace the previous summary)
        use_date_only = True
        
        # Save markdown
        md_content = Formatter.format_markdown(articles, metadata)
        md_path = storage.save_markdown(md_content, use_date_only=use_date_only)
        click.echo(f"✅ Saved markdown: {md_path}")
        
        # Save JSON
        json_data = Formatter.format_json(articles, metadata)
        json_path = storage.save_json(json_data, use_date_only=use_date_only)
        click.echo(f"✅ Saved JSON: {json_path}")
    
    click.echo("\n✨ Done!")


if __name__ == "__main__":
    main()
