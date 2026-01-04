#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Direct test of the refresh functionality to verify LLM calls are working."""

import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from src.agents.scraper_agent import ScraperAgent
from src.agents.filter_agent import FilterAgent
from src.agents.summarizer_agent import SummarizerAgent
from src.utils.storage import Storage
from src.utils.formatters import Formatter
from src.models.llm_client import get_llm_client

def test_refresh():
    """Test the refresh functionality directly."""
    print("=" * 60)
    print("Testing Refresh Functionality")
    print("=" * 60)
    print()
    
    # Check LLM provider
    provider = os.environ.get('LLM_PROVIDER', 'auto')
    print(f"LLM Provider: {provider}")
    print()
    
    # Initialize components
    print("1. Initializing LLM client...")
    try:
        llm_client = get_llm_client(provider=provider)
        print(f"   [OK] LLM client initialized: {type(llm_client).__name__}")
        print(f"   [OK] Provider: {llm_client.provider}")
    except Exception as e:
        print(f"   [FAIL] Failed to initialize LLM client: {e}")
        return False
    print()
    
    # Test LLM call
    print("2. Testing LLM summarize call...")
    try:
        test_text = "This is a test article about technology and AI."
        summary = llm_client.summarize(test_text, max_length=50)
        print(f"   [OK] LLM summarize call successful")
        print(f"   [OK] Summary: {summary[:100]}...")
    except Exception as e:
        print(f"   [FAIL] LLM summarize call failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    print()
    
    # Scrape articles
    print("3. Scraping articles from Hacker News...")
    try:
        scraper = ScraperAgent()
        articles = scraper.scrape_articles_with_comments(top_n=2)
        if not articles:
            print("   ✗ No articles found")
            return False
        print(f"   [OK] Scraped {len(articles)} articles")
        print(f"   [OK] First article: {articles[0]['title'][:60]}...")
    except Exception as e:
        print(f"   [FAIL] Failed to scrape articles: {e}")
        import traceback
        traceback.print_exc()
        return False
    print()
    
    # Classify articles
    print("4. Classifying articles...")
    try:
        filter_agent = FilterAgent(llm_client=llm_client)
        articles = filter_agent.batch_classify(articles)
        print(f"   [OK] Classified {len(articles)} articles")
    except Exception as e:
        print(f"   [FAIL] Failed to classify articles: {e}")
        import traceback
        traceback.print_exc()
        return False
    print()
    
    # Summarize articles (THIS IS THE KEY TEST)
    print("5. Summarizing articles with LLM (this is the critical step)...")
    try:
        summarizer = SummarizerAgent(llm_client=llm_client)
        articles = summarizer.summarize_articles(articles, include_comments=True)
        print(f"   [OK] Summarized {len(articles)} articles")
        
        # Check if summaries were actually generated
        for i, article in enumerate(articles, 1):
            has_summary = article.get('article_summary')
            if has_summary:
                print(f"   [OK] Article {i}: Has summary ({len(has_summary)} chars)")
                print(f"     Preview: {has_summary[:80]}...")
            else:
                print(f"   [FAIL] Article {i}: No summary generated!")
                return False
            
            # Check for comment summary
            if article.get('comment_summary'):
                print(f"   [OK] Article {i}: Has comment summary")
            else:
                print(f"   [WARN] Article {i}: No comment summary (may be normal if no comments)")
    except Exception as e:
        print(f"   [FAIL] Failed to summarize articles: {e}")
        import traceback
        traceback.print_exc()
        return False
    print()
    
    # Save results
    print("6. Saving results...")
    try:
        storage = Storage(output_dir="outputs")
        metadata = {
            "top_n": 2,
            "filter_ai": False,
            "include_comments": True,
            "articles_count": len(articles),
            "llm_provider": provider
        }
        
        md_content = Formatter.format_markdown(articles, metadata)
        md_path = storage.save_markdown(md_content, use_date_only=True)
        print(f"   [OK] Saved markdown: {md_path}")
        
        json_data = Formatter.format_json(articles, metadata)
        json_path = storage.save_json(json_data, use_date_only=True)
        print(f"   [OK] Saved JSON: {json_path}")
    except Exception as e:
        print(f"   [FAIL] Failed to save results: {e}")
        import traceback
        traceback.print_exc()
        return False
    print()
    
    print("=" * 60)
    print("[SUCCESS] ALL TESTS PASSED - Refresh functionality is working!")
    print("=" * 60)
    print()
    print("The LLM is being called and generating real summaries.")
    print("If you're seeing 'Test Article 1' in the UI, it's likely:")
    print("  1. An old test file that needs to be deleted")
    print("  2. The refresh hasn't completed yet (check logs)")
    print("  3. The UI is showing a cached summary")
    print()
    
    return True

if __name__ == "__main__":
    success = test_refresh()
    sys.exit(0 if success else 1)

