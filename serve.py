#!/usr/bin/env python3
"""Simple HTTP server to serve the HackerNews Summary web UI."""

import http.server
import socketserver
import os
import sys
from pathlib import Path

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.resolve()

# Change to the project root directory
os.chdir(PROJECT_ROOT)

# Generate the index first
print("Generating summary index...", flush=True)
sys.path.insert(0, str(PROJECT_ROOT / "web"))
from generate_index import generate_index
generate_index(PROJECT_ROOT)

# Default port - can be overridden by PORT environment variable
DEFAULT_PORT = 8000
# Bind address - use 0.0.0.0 for Docker, localhost for local development
BIND_ADDRESS = os.environ.get('BIND_ADDRESS', '0.0.0.0')


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
