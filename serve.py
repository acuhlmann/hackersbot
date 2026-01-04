#!/usr/bin/env python3
"""Simple HTTP server to serve the HackerNews Summary web UI."""

import http.server
import socketserver
import os
import sys
import json
import threading
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.resolve()

# Change to the project root directory
os.chdir(PROJECT_ROOT)

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


class Handler(http.server.SimpleHTTPRequestHandler):
    """Custom handler to serve files at root path with proper routing."""
    
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
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
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
                    provider = os.environ.get('LLM_PROVIDER', 'auto')
                    
                    # Initialize components
                    print(f"[REFRESH] Initializing LLM client with provider: {provider}", flush=True)
                    llm_client = get_llm_client(provider=provider)
                    print(f"[REFRESH] LLM client initialized: {type(llm_client).__name__}", flush=True)
                    scraper = ScraperAgent()
                    filter_agent = FilterAgent(llm_client=llm_client)
                    summarizer = SummarizerAgent(llm_client=llm_client)
                    storage = Storage(output_dir="outputs")
                    
                    # Scrape articles
                    print(f"[REFRESH] Scraping top {top_n} articles from Hacker News...", flush=True)
                    articles = scraper.scrape_articles_with_comments(top_n)
                    if not articles:
                        raise Exception("No articles found")
                    print(f"[REFRESH] Scraped {len(articles)} articles", flush=True)
                    
                    # Classify articles (but don't filter)
                    print(f"[REFRESH] Classifying articles...", flush=True)
                    articles = filter_agent.batch_classify(articles)
                    
                    # Summarize articles - THIS IS WHERE LLM CALLS HAPPEN
                    print(f"[REFRESH] Summarizing articles with LLM (this may take a while)...", flush=True)
                    articles = summarizer.summarize_articles(articles, include_comments=True)
                    print(f"[REFRESH] Summarization complete. Generated summaries for {len(articles)} articles.", flush=True)
                    
                    # Prepare metadata
                    metadata = {
                        "top_n": top_n,
                        "filter_ai": False,
                        "include_comments": True,
                        "articles_count": len(articles),
                        "llm_provider": provider
                    }
                    
                    # Save to outputs/ directory (date-only format)
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
                    
                except Exception as e:
                    print(f"[REFRESH ERROR] Error during refresh: {e}", flush=True)
                    import traceback
                    print("[REFRESH ERROR] Full traceback:", flush=True)
                    traceback.print_exc()
                    print("[REFRESH ERROR] Refresh failed. Check logs above for details.", flush=True)
                    # Don't raise - let finally block reset the flag
                finally:
                    with refresh_lock:
                        global refresh_in_progress
                        refresh_in_progress = False
            
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
    
    with socketserver.TCPServer((BIND_ADDRESS, port), Handler) as httpd:
        # Display appropriate URL based on bind address
        display_host = "localhost" if BIND_ADDRESS == "0.0.0.0" else BIND_ADDRESS
        url = f"http://{display_host}:{port}/"
        print(f"\nHackerNews Summary UI", flush=True)
        print(f"Serving at: {url}", flush=True)
        print(f"Bound to: {BIND_ADDRESS}:{port}", flush=True)
        print(f"Press Ctrl+C to stop\n", flush=True)
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nShutting down...")
            httpd.shutdown()


if __name__ == "__main__":
    main()
