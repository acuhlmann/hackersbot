"""Tests for the web server (serve.py)."""

import pytest
import http.server
import socketserver
import threading
import time
import urllib.request
import urllib.error
import json
from pathlib import Path

# Import the serve module
import sys
import os
sys.path.insert(0, str(Path(__file__).parent.parent))
from serve import Handler, PROJECT_ROOT


class TestWebServer:
    """Test the web server functionality."""
    
    @pytest.fixture(scope="class")
    def server(self):
        """Start a test server in a separate thread."""
        port = 8888
        httpd = socketserver.TCPServer(("127.0.0.1", port), Handler)
        httpd.allow_reuse_address = True
        
        # Start server in a thread
        server_thread = threading.Thread(target=httpd.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        # Wait for server to start
        time.sleep(0.5)
        
        yield f"http://127.0.0.1:{port}"
        
        # Cleanup
        httpd.shutdown()
        httpd.server_close()
    
    def test_root_path_serves_index_html(self, server):
        """Test that root path serves index.html."""
        url = f"{server}/"
        req = urllib.request.Request(url)
        
        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.getcode() == 200
            assert 'text/html' in response.headers.get('Content-Type', '')
            content = response.read().decode('utf-8')
            assert 'hackersbot' in content.lower()
            assert '<html' in content.lower()
    
    def test_index_html_path_works(self, server):
        """Test that /index.html path also works."""
        url = f"{server}/index.html"
        req = urllib.request.Request(url)
        
        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.getcode() == 200
            assert 'text/html' in response.headers.get('Content-Type', '')
            content = response.read().decode('utf-8')
            assert 'hackersbot' in content.lower()
    
    def test_summaries_index_json(self, server):
        """Test that summaries index.json is accessible."""
        url = f"{server}/summaries/index.json"
        req = urllib.request.Request(url)
        
        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.getcode() == 200
            content = response.read().decode('utf-8')
            data = json.loads(content)
            assert isinstance(data, list)
            assert len(data) > 0
    
    def test_individual_summary_json(self, server):
        """Test that individual summary files are accessible."""
        # Find a summary file
        summaries_dir = PROJECT_ROOT / 'summaries'
        summary_files = list(summaries_dir.glob('*_summary.json'))
        
        if not summary_files:
            pytest.skip("No summary files found")
        
        summary_file = summary_files[0]
        url = f"{server}/summaries/{summary_file.name}"
        req = urllib.request.Request(url)
        
        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.getcode() == 200
            content = response.read().decode('utf-8')
            data = json.loads(content)
            assert 'articles' in data or 'metadata' in data
    
    def test_nonexistent_path_returns_404(self, server):
        """Test that non-existent paths return 404."""
        url = f"{server}/nonexistent/path"
        req = urllib.request.Request(url)
        
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=5)
        assert exc_info.value.code == 404
    
    def test_summaries_path_security(self, server):
        """Test that path traversal attacks are prevented."""
        # Try to access files outside summaries directory
        url = f"{server}/summaries/../serve.py"
        req = urllib.request.Request(url)
        
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=5)
        # Should return 403 Forbidden or 404 Not Found
        assert exc_info.value.code in (403, 404)
    
    def test_api_status_endpoint(self, server):
        """Test that /api/status endpoint works."""
        url = f"{server}/api/status"
        req = urllib.request.Request(url)
        
        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.getcode() == 200
            assert 'application/json' in response.headers.get('Content-Type', '')
            content = response.read().decode('utf-8')
            data = json.loads(content)
            assert 'in_progress' in data
            assert 'can_refresh' in data
            assert 'last_refresh' in data
            assert isinstance(data['in_progress'], bool)
            assert isinstance(data['can_refresh'], bool)
    
    def test_api_refresh_endpoint_exists(self, server):
        """Test that /api/refresh endpoint exists and handles requests."""
        url = f"{server}/api/refresh"
        req = urllib.request.Request(url, method='POST')
        req.add_header('Content-Type', 'application/json')
        
        # This might return 200 (refresh started) or 429 (rate limited)
        # or 409 (already in progress), all are valid responses
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                assert response.getcode() in (200, 409, 429)
                assert 'application/json' in response.headers.get('Content-Type', '')
                content = response.read().decode('utf-8')
                data = json.loads(content)
                assert 'success' in data or 'error' in data
        except urllib.error.HTTPError as e:
            # Rate limit or conflict are acceptable
            assert e.code in (409, 429)
    
    def test_api_invalid_endpoint_returns_404(self, server):
        """Test that invalid API endpoints return 404."""
        url = f"{server}/api/invalid"
        req = urllib.request.Request(url)
        
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=5)
        assert exc_info.value.code == 404

