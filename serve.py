#!/usr/bin/env python3
"""Simple HTTP server to serve the HackerNews Summary web UI."""

import http.server
import socketserver
import os
import sys
import json
import threading
import shutil
import queue
import re
import time
from collections import deque
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple, List
from dotenv import load_dotenv

# URL validation pattern for HN article URLs
HN_URL_PATTERN = re.compile(r'^https?://(www\.)?news\.ycombinator\.com/item\?id=(\d+)$')

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.resolve()

# Change to the project root directory
os.chdir(PROJECT_ROOT)

# Load environment variables from .env file (not .env.example - that's just a template)
# In production (GitHub Actions, GCP VM), environment variables are injected directly
# so .env file won't exist and load_dotenv() will silently continue
try:
    load_dotenv(dotenv_path=str(PROJECT_ROOT / '.env'))  # Explicitly load from project root
except Exception as e:
    # If .env file has encoding issues, log warning but continue
    # Production environments use injected env vars, so this is fine
    print(f"Warning: Could not load .env file: {e}. Continuing with environment variables.", flush=True)

# Generate the index first (handle errors gracefully)
print("Generating summary index...", flush=True)
try:
    sys.path.insert(0, str(PROJECT_ROOT / "web"))
    from generate_index import generate_index
    generate_index(PROJECT_ROOT)
except Exception as e:
    print(f"Warning: Could not generate index: {e}", flush=True)
    # Continue anyway - index will be generated on first refresh

# Default port - can be overridden by PORT environment variable
DEFAULT_PORT = 8000
# Bind address - use 0.0.0.0 for Docker, localhost for local development
BIND_ADDRESS = os.environ.get('BIND_ADDRESS', '0.0.0.0')

# Global state for refresh management
refresh_lock = threading.Lock()
refresh_in_progress = False

# Broadcast stream state (SSE subscribers)
subscribers_lock = threading.Lock()
refresh_subscribers: List["queue.Queue[Dict[str, Any]]"] = []
refresh_event_history: "deque[Dict[str, Any]]" = deque(maxlen=300)


def _broadcast_refresh_event(payload: Dict[str, Any]) -> None:
    """Fan-out refresh progress events to all active subscribers."""
    try:
        refresh_event_history.append(payload)
    except Exception:
        pass
    with subscribers_lock:
        subscribers = list(refresh_subscribers)
    if not subscribers:
        return
    for q in subscribers:
        try:
            q.put_nowait(payload)
        except queue.Full:
            # Drop oldest to make room, then try once more.
            try:
                _ = q.get_nowait()
            except queue.Empty:
                pass
            try:
                q.put_nowait(payload)
            except queue.Full:
                # If still full, drop this event.
                pass


def generate_adhoc_index(base_dir: Path) -> List[Dict[str, Any]]:
    """Generate index.json for ad-hoc summaries."""
    adhoc_dir = base_dir / "summaries" / "adhoc"
    adhoc_dir.mkdir(parents=True, exist_ok=True)
    
    summaries = []
    
    # Find all JSON summary files in adhoc directory
    for json_file in sorted(adhoc_dir.glob("*_summary.json"), reverse=True):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            article = data.get('article', {})
            summaries.append({
                "itemId": data.get('item_id', json_file.stem.replace('_summary', '')),
                "title": article.get('title', 'Unknown Title'),
                "url": article.get('url', ''),
                "hnUrl": data.get('hn_url', f"https://news.ycombinator.com/item?id={data.get('item_id', '')}"),
                "jsonFile": json_file.name,
                "generatedAt": data.get('generated_at'),
                "points": article.get('points', 0),
                "commentCount": article.get('comment_count', 0)
            })
        except Exception as e:
            print(f"Warning: Could not read adhoc summary {json_file}: {e}", flush=True)
            continue
    
    # Sort by generatedAt descending (newest first)
    summaries.sort(key=lambda x: x.get('generatedAt', ''), reverse=True)
    
    # Write the index
    index_path = adhoc_dir / "index.json"
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(summaries, f, indent=2)
    
    print(f"Generated adhoc index.json with {len(summaries)} summaries", flush=True)
    return summaries


# Daily scheduler state
scheduler_last_run_date: Optional[str] = None
scheduler_lock = threading.Lock()


def run_scheduled_refresh():
    """Run the daily refresh (called by scheduler)."""
    global refresh_in_progress
    
    with refresh_lock:
        if refresh_in_progress:
            print("[SCHEDULER] Refresh already in progress, skipping scheduled run", flush=True)
            return
        refresh_in_progress = True
    
    try:
        print("[SCHEDULER] Starting scheduled daily refresh...", flush=True)
        _broadcast_refresh_event({"type": "log", "level": "info", "message": "Starting scheduled daily refresh..."})
        
        # Import components
        sys.path.insert(0, str(PROJECT_ROOT))
        from src.agents.scraper_agent import ScraperAgent
        from src.agents.filter_agent import FilterAgent
        from src.agents.summarizer_agent import SummarizerAgent
        from src.utils.storage import Storage
        from src.utils.formatters import Formatter
        from src.models.llm_client import get_llm_client
        
        # Default parameters
        top_n = 5
        
        # Initialize components
        print("[SCHEDULER] Initializing DeepSeek LLM client...", flush=True)
        llm_client = get_llm_client(event_handler=_broadcast_refresh_event)
        scraper = ScraperAgent()
        filter_agent = FilterAgent(llm_client=llm_client)
        summarizer = SummarizerAgent(llm_client=llm_client)
        storage = Storage(output_dir="outputs")
        
        # Scrape articles
        print(f"[SCHEDULER] Scraping top {top_n} articles from Hacker News...", flush=True)
        articles = scraper.scrape_articles_with_comments(top_n)
        if not articles:
            raise Exception("No articles found")
        print(f"[SCHEDULER] Scraped {len(articles)} articles", flush=True)
        
        # Classify articles
        print(f"[SCHEDULER] Classifying articles...", flush=True)
        articles = filter_agent.batch_classify(articles)
        
        # Summarize articles
        print(f"[SCHEDULER] Summarizing articles...", flush=True)
        articles = summarizer.summarize_articles(articles, include_comments=True)
        print(f"[SCHEDULER] Summarization complete.", flush=True)
        
        # Prepare metadata
        metadata = {
            "top_n": top_n,
            "filter_ai": False,
            "include_comments": True,
            "articles_count": len(articles),
            "llm_provider": "deepseek",
            "scheduled": True
        }
        
        # Save files
        md_content = Formatter.format_markdown(articles, metadata)
        md_path = storage.save_markdown(md_content, use_date_only=True)
        
        json_data = Formatter.format_json(articles, metadata)
        json_path = storage.save_json(json_data, use_date_only=True)
        
        # Copy to summaries/ directory
        summaries_dir = PROJECT_ROOT / "summaries"
        summaries_dir.mkdir(exist_ok=True)
        shutil.copy2(md_path, summaries_dir / Path(md_path).name)
        shutil.copy2(json_path, summaries_dir / Path(json_path).name)
        
        # Regenerate index
        generate_index(PROJECT_ROOT)
        
        print("[SCHEDULER] Scheduled refresh complete!", flush=True)
        _broadcast_refresh_event({"type": "done", "level": "info", "message": "Scheduled refresh complete"})
        
    except Exception as e:
        print(f"[SCHEDULER ERROR] Error during scheduled refresh: {e}", flush=True)
        _broadcast_refresh_event({"type": "refresh_error", "level": "error", "message": f"Scheduled refresh failed: {e}"})
        import traceback
        traceback.print_exc()
    finally:
        with refresh_lock:
            refresh_in_progress = False


def daily_scheduler_thread():
    """
    Background thread that triggers daily refresh at 6:00 AM GMT+8.
    
    GMT+8 is 8 hours ahead of UTC, so 6:00 AM GMT+8 = 22:00 UTC (previous day).
    """
    global scheduler_last_run_date
    
    # GMT+8 offset
    GMT8 = timezone(timedelta(hours=8))
    
    print("[SCHEDULER] Daily scheduler started. Will run at 6:00 AM GMT+8", flush=True)
    
    while True:
        try:
            # Get current time in GMT+8
            now_gmt8 = datetime.now(GMT8)
            current_date_gmt8 = now_gmt8.strftime("%Y-%m-%d")
            current_hour = now_gmt8.hour
            current_minute = now_gmt8.minute
            
            with scheduler_lock:
                should_run = (
                    current_hour == 6 and 
                    current_minute < 5 and  # Run within first 5 minutes of 6 AM
                    scheduler_last_run_date != current_date_gmt8
                )
                
                if should_run:
                    scheduler_last_run_date = current_date_gmt8
            
            if should_run:
                print(f"[SCHEDULER] Triggering scheduled refresh at {now_gmt8.isoformat()}", flush=True)
                # Run in a separate thread to not block the scheduler loop
                refresh_thread = threading.Thread(target=run_scheduled_refresh, daemon=True)
                refresh_thread.start()
            
        except Exception as e:
            print(f"[SCHEDULER ERROR] Error in scheduler loop: {e}", flush=True)
        
        # Sleep for 1 minute before checking again
        time.sleep(60)


class Handler(http.server.SimpleHTTPRequestHandler):
    """Custom handler to serve files at root path with proper routing."""

    # EventSource / SSE works much more reliably with HTTP/1.1
    protocol_version = "HTTP/1.1"
    
    def do_GET(self):
        """Handle GET requests with custom routing."""
        # Parse the path
        path = self.path.split('?')[0]  # Remove query string
        
        # Route requests appropriately
        if path == '/' or path == '/index.html':
            # Serve web/index.html at root
            self.serve_file(PROJECT_ROOT / 'web' / 'index.html')
        elif path == '/api/status':
            # API endpoint for refresh status
            self.handle_status()
        elif path == '/api/refresh/stream':
            # SSE stream of refresh progress events
            self.handle_refresh_stream()
        elif path == '/api/adhoc-summaries':
            # Get ad-hoc summaries index
            self.handle_adhoc_summaries()
        elif path == '/api/adhoc-status':
            # Get ad-hoc refresh status (daily limit info)
            self.handle_adhoc_status()
        elif path.startswith('/summaries/'):
            # Serve files from summaries directory
            file_path = PROJECT_ROOT / path[1:]  # Remove leading /
            # Security: ensure path is within summaries directory
            try:
                file_path.resolve().relative_to(PROJECT_ROOT.resolve() / 'summaries')
            except ValueError:
                self.send_error(403, "Forbidden")
                return
            if file_path.exists() and file_path.is_file():
                self.serve_file(file_path)
            else:
                self.send_error(404, "File not found")
        else:
            # Serve files from web directory (for any other assets)
            file_path = PROJECT_ROOT / 'web' / path[1:] if path.startswith('/') else PROJECT_ROOT / 'web' / path
            # Security: ensure path is within web directory
            try:
                file_path.resolve().relative_to(PROJECT_ROOT.resolve() / 'web')
            except ValueError:
                self.send_error(403, "Forbidden")
                return
            if file_path.exists() and file_path.is_file():
                self.serve_file(file_path)
            else:
                self.send_error(404, "File not found")
    
    def do_POST(self):
        """Handle POST requests for API endpoints."""
        path = self.path.split('?')[0]  # Remove query string
        
        if path == '/api/refresh':
            self.handle_refresh()
        elif path == '/api/summarize-single':
            self.handle_summarize_single()
        else:
            self.send_error(404, "Not Found")
    
    def serve_file(self, file_path):
        """Serve a file with proper headers."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Determine content type
            content_type = self.guess_type(str(file_path))
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', content_type)
            # With HTTP/1.1, ensure clients know response length.
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error serving file: {str(e)}")
    
    def end_headers(self):
        # Add CORS headers for local development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def send_json_response(self, data: Dict[str, Any], status_code: int = 200):
        """Send JSON response."""
        body = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def get_today_summary(self) -> Optional[Dict[str, Any]]:
        """Get today's summary file if it exists."""
        today = datetime.now().strftime("%Y-%m-%d")
        summaries_dir = PROJECT_ROOT / "summaries"
        json_file = summaries_dir / f"{today}_summary.json"
        
        if json_file.exists():
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return None
    
    def check_rate_limit(self) -> Tuple[bool, Optional[str]]:
        """
        Check if refresh is allowed (rate limit: once per hour).
        Returns (allowed, error_message).
        """
        today_summary = self.get_today_summary()
        if not today_summary:
            return True, None
        
        generated_at_str = today_summary.get('generated_at')
        if not generated_at_str:
            return True, None
        
        try:
            # Parse ISO format timestamp
            generated_at_str_clean = generated_at_str.replace('Z', '+00:00')
            generated_at = datetime.fromisoformat(generated_at_str_clean)
            
            # Convert to UTC for comparison if timezone-aware
            if generated_at.tzinfo:
                from datetime import timezone
                generated_at = generated_at.astimezone(timezone.utc)
                now = datetime.now(timezone.utc)
            else:
                now = datetime.now()
            
            time_diff = now - generated_at
            if time_diff.total_seconds() < 3600:  # Less than 1 hour
                remaining = int(3600 - time_diff.total_seconds())
                minutes = remaining // 60
                seconds = remaining % 60
                return False, f"Rate limit: Please wait {minutes}m {seconds}s before refreshing again"
        except Exception as e:
            # If we can't parse the timestamp, allow the refresh
            print(f"Warning: Could not parse generated_at timestamp: {e}", flush=True)
            return True, None
        
        return True, None
    
    def check_adhoc_rate_limit(self, item_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if adhoc summarization is allowed for a specific item (rate limit: once per hour).
        Returns (allowed, error_message).
        """
        adhoc_dir = PROJECT_ROOT / "summaries" / "adhoc"
        existing_json = adhoc_dir / f"{item_id}_summary.json"
        
        if not existing_json.exists():
            return True, None
        
        try:
            with open(existing_json, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            generated_at_str = existing_data.get('generated_at')
            if not generated_at_str:
                return True, None
            
            # Parse ISO format timestamp
            generated_at_str_clean = generated_at_str.replace('Z', '+00:00')
            generated_at = datetime.fromisoformat(generated_at_str_clean)
            
            # Convert to UTC for comparison if timezone-aware
            if generated_at.tzinfo:
                from datetime import timezone
                generated_at = generated_at.astimezone(timezone.utc)
                now = datetime.now(timezone.utc)
            else:
                now = datetime.now()
            
            time_diff = now - generated_at
            if time_diff.total_seconds() < 3600:  # Less than 1 hour
                remaining = int(3600 - time_diff.total_seconds())
                minutes = remaining // 60
                seconds = remaining % 60
                return False, f"Rate limit: Please wait {minutes}m {seconds}s before re-summarizing this article"
        except Exception as e:
            # If we can't parse the timestamp, allow the refresh
            print(f"Warning: Could not parse generated_at timestamp for item {item_id}: {e}", flush=True)
            return True, None
        
        return True, None
    
    def count_adhoc_refreshes_today(self) -> int:
        """Count how many adhoc summaries were refreshed/created today."""
        adhoc_dir = PROJECT_ROOT / "summaries" / "adhoc"
        if not adhoc_dir.exists():
            return 0
        
        today = datetime.now().strftime("%Y-%m-%d")
        count = 0
        
        for json_file in adhoc_dir.glob("*_summary.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                generated_at_str = data.get('generated_at', '')
                if generated_at_str.startswith(today):
                    count += 1
            except Exception:
                continue
        
        return count
    
    def check_adhoc_daily_limit(self) -> Tuple[bool, int, Optional[str]]:
        """
        Check if daily adhoc refresh limit (5 per day) has been reached.
        Returns (allowed, remaining_count, error_message).
        """
        daily_limit = 5
        count_today = self.count_adhoc_refreshes_today()
        remaining = daily_limit - count_today
        
        if remaining <= 0:
            return False, 0, f"Daily limit reached: You can refresh up to {daily_limit} articles per day. Try again tomorrow."
        
        return True, remaining, None
    
    def handle_status(self):
        """Handle GET /api/status - return refresh status and last refresh time."""
        # Note: We read refresh_in_progress but don't modify it, so no global needed
        today_summary = self.get_today_summary()
        status_data = {
            "in_progress": refresh_in_progress,
            "last_refresh": None,
            "can_refresh": True,
            "rate_limit_message": None
        }
        
        if today_summary:
            generated_at_str = today_summary.get('generated_at')
            if generated_at_str:
                status_data["last_refresh"] = generated_at_str
                can_refresh, error_msg = self.check_rate_limit()
                status_data["can_refresh"] = can_refresh
                status_data["rate_limit_message"] = error_msg
        
        self.send_json_response(status_data)
    
    def handle_refresh(self):
        """Handle POST /api/refresh - trigger summary generation."""
        global refresh_in_progress
        
        # Check if refresh is already in progress
        with refresh_lock:
            if refresh_in_progress:
                self.send_json_response({
                    "success": False,
                    "error": "Refresh already in progress"
                }, status_code=409)
                return
            
            # Check rate limit
            can_refresh, error_msg = self.check_rate_limit()
            if not can_refresh:
                self.send_json_response({
                    "success": False,
                    "error": error_msg
                }, status_code=429)
                return
            
            refresh_in_progress = True
        
        try:
            # Run the summarizer in a background thread to avoid blocking
            def run_refresh():
                global refresh_in_progress
                try:
                    # Import here to avoid circular imports
                    sys.path.insert(0, str(PROJECT_ROOT))
                    from src.agents.scraper_agent import ScraperAgent
                    from src.agents.filter_agent import FilterAgent
                    from src.agents.summarizer_agent import SummarizerAgent
                    from src.utils.storage import Storage
                    from src.utils.formatters import Formatter
                    from src.models.llm_client import get_llm_client
                    
                    # Default parameters for refresh
                    top_n = 5
                    
                    # Initialize components
                    print("[REFRESH] Initializing DeepSeek LLM client...", flush=True)
                    _broadcast_refresh_event({"type": "log", "level": "info", "message": "Initializing DeepSeek LLM client..."})
                    llm_client = get_llm_client(event_handler=_broadcast_refresh_event)
                    print("[REFRESH] LLM client initialized", flush=True)
                    _broadcast_refresh_event({"type": "log", "level": "info", "message": "DeepSeek LLM client ready"})
                    scraper = ScraperAgent()
                    filter_agent = FilterAgent(llm_client=llm_client)
                    summarizer = SummarizerAgent(llm_client=llm_client)
                    storage = Storage(output_dir="outputs")
                    
                    # Scrape articles
                    print(f"[REFRESH] Scraping top {top_n} articles from Hacker News...", flush=True)
                    _broadcast_refresh_event({"type": "log", "level": "info", "message": f"Scraping top {top_n} Hacker News articles..."})
                    articles = scraper.scrape_articles_with_comments(top_n)
                    if not articles:
                        raise Exception("No articles found")
                    print(f"[REFRESH] Scraped {len(articles)} articles", flush=True)
                    _broadcast_refresh_event({"type": "log", "level": "info", "message": f"Scraped {len(articles)} articles"})
                    
                    # Classify articles (but don't filter)
                    print(f"[REFRESH] Classifying articles...", flush=True)
                    _broadcast_refresh_event({"type": "log", "level": "info", "message": "Classifying articles (AI-related or not)..."})
                    articles = filter_agent.batch_classify(articles)
                    
                    # Summarize articles - THIS IS WHERE LLM CALLS HAPPEN
                    print(f"[REFRESH] Summarizing articles with LLM (this may take a while)...", flush=True)
                    _broadcast_refresh_event({"type": "log", "level": "info", "message": "Summarizing articles (LLM)…"})
                    articles = summarizer.summarize_articles(articles, include_comments=True)
                    print(f"[REFRESH] Summarization complete. Generated summaries for {len(articles)} articles.", flush=True)
                    _broadcast_refresh_event({"type": "log", "level": "info", "message": f"Summarization complete ({len(articles)} articles)"})
                    
                    # Prepare metadata
                    metadata = {
                        "top_n": top_n,
                        "filter_ai": False,
                        "include_comments": True,
                        "articles_count": len(articles),
                        "llm_provider": "deepseek"
                    }
                    
                    # Save to outputs/ directory (date-only format)
                    _broadcast_refresh_event({"type": "log", "level": "info", "message": "Saving summary files..."})
                    md_content = Formatter.format_markdown(articles, metadata)
                    md_path = storage.save_markdown(md_content, use_date_only=True)
                    
                    json_data = Formatter.format_json(articles, metadata)
                    json_path = storage.save_json(json_data, use_date_only=True)
                    
                    # Copy to summaries/ directory
                    summaries_dir = PROJECT_ROOT / "summaries"
                    summaries_dir.mkdir(exist_ok=True)
                    shutil.copy2(md_path, summaries_dir / Path(md_path).name)
                    shutil.copy2(json_path, summaries_dir / Path(json_path).name)
                    
                    # Regenerate index
                    generate_index(PROJECT_ROOT)
                    _broadcast_refresh_event({"type": "done", "level": "info", "message": "Refresh complete"})
                    
                except Exception as e:
                    print(f"[REFRESH ERROR] Error during refresh: {e}", flush=True)
                    _broadcast_refresh_event({"type": "refresh_error", "level": "error", "message": f"Refresh failed: {e}"})
                    import traceback
                    print("[REFRESH ERROR] Full traceback:", flush=True)
                    traceback.print_exc()
                    print("[REFRESH ERROR] Refresh failed. Check logs above for details.", flush=True)
                    # Don't raise - let finally block reset the flag
                finally:
                    with refresh_lock:
                        global refresh_in_progress
                        refresh_in_progress = False
                        _broadcast_refresh_event({"type": "log", "level": "info", "message": "Refresh flag cleared"})
            
            # Start refresh in background thread
            refresh_thread = threading.Thread(target=run_refresh, daemon=True)
            refresh_thread.start()
            
            # Return immediately with success
            self.send_json_response({
                "success": True,
                "message": "Refresh started"
            })
            
        except Exception as e:
            with refresh_lock:
                refresh_in_progress = False
            self.send_json_response({
                "success": False,
                "error": str(e)
            }, status_code=500)

    def handle_summarize_single(self):
        """Handle POST /api/summarize-single - summarize a single HN article."""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            url = data.get('url', '').strip()
            if not url:
                self.send_json_response({
                    "success": False,
                    "error": "URL is required"
                }, status_code=400)
                return
            
            # Validate URL format
            match = HN_URL_PATTERN.match(url)
            if not match:
                self.send_json_response({
                    "success": False,
                    "error": "Invalid URL. Must be a Hacker News item URL (e.g., https://news.ycombinator.com/item?id=12345)"
                }, status_code=400)
                return
            
            item_id = match.group(2)
            
            # Check daily limit (5 refreshes per day across all articles)
            can_refresh_daily, remaining, daily_error = self.check_adhoc_daily_limit()
            if not can_refresh_daily:
                self.send_json_response({
                    "success": False,
                    "error": daily_error
                }, status_code=429)
                return
            
            # Check per-article rate limit (once per hour for the same article)
            can_summarize, error_msg = self.check_adhoc_rate_limit(item_id)
            if not can_summarize:
                self.send_json_response({
                    "success": False,
                    "error": error_msg
                }, status_code=429)
                return
            
            # Always re-summarize if rate limit allows (will replace existing if it exists)
            adhoc_dir = PROJECT_ROOT / "summaries" / "adhoc"
            adhoc_dir.mkdir(parents=True, exist_ok=True)
            existing_json = adhoc_dir / f"{item_id}_summary.json"
            
            # Run summarization synchronously (single article is fast enough)
            print(f"[ADHOC] Summarizing single article: {item_id}", flush=True)
            
            # Ensure .env is loaded before importing modules that need it
            # Use override=True to reload in case it was already loaded
            try:
                env_path = PROJECT_ROOT / '.env'
                load_dotenv(dotenv_path=str(env_path), override=True)
                # Verify the API key is accessible
                api_key = os.getenv("DEEPSEEK_API_KEY")
                if not api_key:
                    self.send_json_response({
                        "success": False,
                        "error": "DEEPSEEK_API_KEY not found in environment. Please check your .env file."
                    }, status_code=500)
                    return
                print(f"[ADHOC] API key loaded (length: {len(api_key)})", flush=True)
            except Exception as e:
                print(f"[ADHOC] Error loading .env file: {e}", flush=True)
                self.send_json_response({
                    "success": False,
                    "error": f"Could not load .env file: {e}. Please ensure it's UTF-8 encoded."
                }, status_code=500)
                return
            
            # Import components
            sys.path.insert(0, str(PROJECT_ROOT))
            from src.agents.scraper_agent import ScraperAgent
            from src.agents.filter_agent import FilterAgent
            from src.agents.summarizer_agent import SummarizerAgent
            from src.utils.formatters import Formatter
            from src.models.llm_client import get_llm_client
            
            llm_client = get_llm_client()
            
            scraper = ScraperAgent()
            filter_agent = FilterAgent(llm_client=llm_client)
            summarizer = SummarizerAgent(llm_client=llm_client)
            
            # Scrape the article
            print(f"[ADHOC] Scraping article {item_id}...", flush=True)
            article = scraper.scrape_single_article(item_id)
            
            if not article:
                self.send_json_response({
                    "success": False,
                    "error": f"Could not fetch article with ID {item_id}. It may not exist or be accessible."
                }, status_code=404)
                return
            
            # Classify article
            print(f"[ADHOC] Classifying article...", flush=True)
            articles = filter_agent.batch_classify([article])
            article = articles[0]
            
            # Summarize article
            print(f"[ADHOC] Summarizing article...", flush=True)
            article = summarizer.summarize_article(article, include_comments=True)
            
            # Prepare data for saving
            summary_data = {
                "item_id": item_id,
                "hn_url": url,
                "generated_at": datetime.now().isoformat(),
                "metadata": {
                    "llm_provider": "deepseek",
                    "include_comments": True
                },
                "article": article
            }
            
            # Save JSON
            with open(existing_json, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2, ensure_ascii=False)
            
            # Save Markdown
            md_content = Formatter.format_markdown([article], summary_data["metadata"])
            md_path = adhoc_dir / f"{item_id}_summary.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            # Regenerate adhoc index
            generate_adhoc_index(PROJECT_ROOT)
            
            print(f"[ADHOC] Successfully summarized article {item_id}", flush=True)
            
            self.send_json_response({
                "success": True,
                "message": "Article summarized successfully",
                "cached": False,
                "data": summary_data
            })
            
        except json.JSONDecodeError:
            self.send_json_response({
                "success": False,
                "error": "Invalid JSON in request body"
            }, status_code=400)
        except Exception as e:
            print(f"[ADHOC ERROR] Error summarizing article: {e}", flush=True)
            import traceback
            traceback.print_exc()
            self.send_json_response({
                "success": False,
                "error": str(e)
            }, status_code=500)

    def handle_adhoc_summaries(self):
        """Handle GET /api/adhoc-summaries - return the ad-hoc summaries index."""
        adhoc_index_path = PROJECT_ROOT / "summaries" / "adhoc" / "index.json"
        
        if adhoc_index_path.exists():
            try:
                with open(adhoc_index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.send_json_response(data)
            except Exception as e:
                self.send_json_response({
                    "error": f"Failed to read adhoc index: {e}"
                }, status_code=500)
        else:
            # Return empty list if no adhoc summaries yet
            self.send_json_response([])
    
    def handle_adhoc_status(self):
        """Handle GET /api/adhoc-status - return adhoc refresh status."""
        can_refresh, remaining, error_msg = self.check_adhoc_daily_limit()
        self.send_json_response({
            "can_refresh": can_refresh,
            "remaining_today": remaining,
            "daily_limit": 5,
            "error_message": error_msg
        })

    def handle_refresh_stream(self):
        """Handle GET /api/refresh/stream - stream refresh progress (SSE)."""
        # Create per-connection queue
        q: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=200)
        with subscribers_lock:
            refresh_subscribers.append(q)

        try:
            self.send_response(200)
            self.send_header('Content-type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            # Best-effort: ask reverse proxies not to buffer SSE
            self.send_header('X-Accel-Buffering', 'no')
            self.end_headers()

            # Initial snapshot
            initial = {
                "type": "status",
                "in_progress": refresh_in_progress,
                "message": "connected",
            }
            self._sse_send(initial, event_name="status")

            # Replay a small tail of recent events so the UI doesn't miss
            # early logs if it subscribes slightly after refresh starts.
            try:
                tail = list(refresh_event_history)[-50:]
                for payload in tail:
                    event_name = str(payload.get("type") or "log")
                    self._sse_send(payload, event_name=event_name)
            except Exception:
                pass

            # Stream loop
            while True:
                try:
                    payload = q.get(timeout=15)
                except queue.Empty:
                    # Heartbeat to keep intermediaries from buffering/closing.
                    try:
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        break
                    continue

                event_name = str(payload.get("type") or "log")
                self._sse_send(payload, event_name=event_name)

                if event_name in ("done", "refresh_error"):
                    # End the stream on completion/failure.
                    break

        finally:
            with subscribers_lock:
                if q in refresh_subscribers:
                    refresh_subscribers.remove(q)

    def _sse_send(self, payload: Dict[str, Any], *, event_name: str) -> None:
        """Send one SSE message."""
        try:
            data = json.dumps(payload, ensure_ascii=False)
            msg = f"event: {event_name}\ndata: {data}\n\n"
            self.wfile.write(msg.encode("utf-8"))
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            raise
    
    def log_message(self, format, *args):
        # Quieter logging - only show errors
        if '200' in str(args) or '304' in str(args):
            return
        print(f"  {args[0]}", flush=True)


def main():
    # Priority: command line arg > PORT env var > default
    port = DEFAULT_PORT
    
    # Check environment variable first
    env_port = os.environ.get('PORT')
    if env_port:
        try:
            port = int(env_port)
        except ValueError:
            pass
    
    # Command line argument overrides environment variable
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    # Use allow_reuse_address to avoid port conflicts
    socketserver.TCPServer.allow_reuse_address = True
    
    # Start the daily scheduler thread
    scheduler = threading.Thread(target=daily_scheduler_thread, daemon=True)
    scheduler.start()
    
    # Use a threaded server so SSE refresh streams don't block other requests.
    with socketserver.ThreadingTCPServer((BIND_ADDRESS, port), Handler) as httpd:
        # Display appropriate URL based on bind address
        display_host = "localhost" if BIND_ADDRESS == "0.0.0.0" else BIND_ADDRESS
        url = f"http://{display_host}:{port}/"
        print(f"\nHackerNews Summary UI", flush=True)
        print(f"Serving at: {url}", flush=True)
        print(f"Bound to: {BIND_ADDRESS}:{port}", flush=True)
        print(f"Daily refresh scheduled at 6:00 AM GMT+8", flush=True)
        print(f"Press Ctrl+C to stop\n", flush=True)
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nShutting down...")
            httpd.shutdown()


if __name__ == "__main__":
    main()
