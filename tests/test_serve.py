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
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

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
        # Find an available port dynamically
        port = None
        for test_port in range(8888, 8988):
            try:
                httpd = socketserver.TCPServer(("127.0.0.1", test_port), Handler)
                httpd.allow_reuse_address = True
                port = test_port
                break
            except OSError:
                continue
        
        if port is None:
            pytest.fail("Could not find an available port for test server")
        
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


class TestRateLimiting:
    """Test the rate limiting functionality."""
    
    def test_rate_limit_allows_refresh_when_no_summary_exists(self):
        """Test that refresh is allowed when no summary exists for today."""
        handler = MagicMock(spec=Handler)
        handler.get_today_summary = MagicMock(return_value=None)
        
        # Call the actual method
        result = Handler.check_rate_limit(handler)
        assert result == (True, None), "Should allow refresh when no summary exists"
    
    def test_rate_limit_allows_refresh_when_no_generated_at(self):
        """Test that refresh is allowed when summary has no generated_at."""
        handler = MagicMock(spec=Handler)
        handler.get_today_summary = MagicMock(return_value={"articles": []})
        
        result = Handler.check_rate_limit(handler)
        assert result == (True, None), "Should allow refresh when no generated_at"
    
    def test_rate_limit_allows_refresh_after_one_hour(self):
        """Test that refresh is allowed when more than 1 hour has passed."""
        handler = MagicMock(spec=Handler)
        
        # Set generated_at to 2 hours ago (naive datetime)
        two_hours_ago = datetime.now() - timedelta(hours=2)
        handler.get_today_summary = MagicMock(return_value={
            "generated_at": two_hours_ago.isoformat()
        })
        
        result = Handler.check_rate_limit(handler)
        assert result[0] is True, f"Should allow refresh after 2 hours, got: {result}"
        assert result[1] is None, f"Should have no error message, got: {result[1]}"
    
    def test_rate_limit_allows_refresh_after_one_hour_with_utc_timezone(self):
        """Test that refresh is allowed when more than 1 hour has passed (UTC timezone)."""
        handler = MagicMock(spec=Handler)
        
        # Set generated_at to 2 hours ago (UTC)
        two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
        handler.get_today_summary = MagicMock(return_value={
            "generated_at": two_hours_ago.isoformat()
        })
        
        result = Handler.check_rate_limit(handler)
        assert result[0] is True, f"Should allow refresh after 2 hours (UTC), got: {result}"
        assert result[1] is None, f"Should have no error message, got: {result[1]}"
    
    def test_rate_limit_blocks_refresh_within_one_hour(self):
        """Test that refresh is blocked when less than 1 hour has passed."""
        handler = MagicMock(spec=Handler)
        
        # Set generated_at to 30 minutes ago
        thirty_minutes_ago = datetime.now() - timedelta(minutes=30)
        handler.get_today_summary = MagicMock(return_value={
            "generated_at": thirty_minutes_ago.isoformat()
        })
        
        result = Handler.check_rate_limit(handler)
        assert result[0] is False, f"Should block refresh within 1 hour, got: {result}"
        assert result[1] is not None, "Should have rate limit message"
        assert "Rate limit" in result[1], f"Message should mention rate limit, got: {result[1]}"
    
    def test_rate_limit_blocks_refresh_within_one_hour_utc(self):
        """Test that refresh is blocked when less than 1 hour has passed (UTC)."""
        handler = MagicMock(spec=Handler)
        
        # Set generated_at to 30 minutes ago (UTC)
        thirty_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=30)
        handler.get_today_summary = MagicMock(return_value={
            "generated_at": thirty_minutes_ago.isoformat()
        })
        
        result = Handler.check_rate_limit(handler)
        assert result[0] is False, f"Should block refresh within 1 hour (UTC), got: {result}"
        assert result[1] is not None, "Should have rate limit message"
    
    def test_rate_limit_allows_refresh_at_exactly_one_hour(self):
        """Test that refresh is allowed at exactly 1 hour (edge case)."""
        handler = MagicMock(spec=Handler)
        
        # Set generated_at to exactly 1 hour and 1 second ago
        one_hour_ago = datetime.now() - timedelta(hours=1, seconds=1)
        handler.get_today_summary = MagicMock(return_value={
            "generated_at": one_hour_ago.isoformat()
        })
        
        result = Handler.check_rate_limit(handler)
        assert result[0] is True, f"Should allow refresh at 1+ hour, got: {result}"
    
    def test_rate_limit_with_z_suffix_timestamp(self):
        """Test that timestamps with Z suffix are handled correctly."""
        handler = MagicMock(spec=Handler)
        
        # Set generated_at to 2 hours ago with Z suffix (UTC)
        two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
        timestamp = two_hours_ago.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
        handler.get_today_summary = MagicMock(return_value={
            "generated_at": timestamp
        })
        
        result = Handler.check_rate_limit(handler)
        assert result[0] is True, f"Should handle Z suffix timestamp, got: {result}"
    
    def test_rate_limit_with_invalid_timestamp_allows_refresh(self):
        """Test that invalid timestamps allow refresh (fail-safe behavior)."""
        handler = MagicMock(spec=Handler)
        
        handler.get_today_summary = MagicMock(return_value={
            "generated_at": "invalid-timestamp"
        })
        
        result = Handler.check_rate_limit(handler)
        assert result[0] is True, f"Should allow refresh with invalid timestamp, got: {result}"


class TestApiStatusEndpoint:
    """Test the /api/status endpoint behavior."""
    
    @pytest.fixture(scope="class")
    def server(self):
        """Start a test server in a separate thread."""
        # Find an available port dynamically
        port = None
        for test_port in range(9000, 9100):
            try:
                httpd = socketserver.TCPServer(("127.0.0.1", test_port), Handler)
                httpd.allow_reuse_address = True
                port = test_port
                break
            except OSError:
                continue
        
        if port is None:
            pytest.fail("Could not find an available port for test server")
        
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
    
    def test_status_returns_correct_structure(self, server):
        """Test that status endpoint returns the expected structure."""
        url = f"{server}/api/status"
        req = urllib.request.Request(url)
        
        with urllib.request.urlopen(req, timeout=5) as response:
            assert response.getcode() == 200
            content = response.read().decode('utf-8')
            data = json.loads(content)
            
            # Verify all required fields exist
            assert 'in_progress' in data
            assert 'can_refresh' in data
            assert 'last_refresh' in data
            assert 'rate_limit_message' in data
            
            # Verify types
            assert isinstance(data['in_progress'], bool)
            assert isinstance(data['can_refresh'], bool)
            # last_refresh can be None or string
            assert data['last_refresh'] is None or isinstance(data['last_refresh'], str)
            # rate_limit_message can be None or string
            assert data['rate_limit_message'] is None or isinstance(data['rate_limit_message'], str)
    
    def test_status_reflects_can_refresh_correctly(self, server):
        """Test that can_refresh is based on rate limiting."""
        url = f"{server}/api/status"
        req = urllib.request.Request(url)
        
        with urllib.request.urlopen(req, timeout=5) as response:
            content = response.read().decode('utf-8')
            data = json.loads(content)
            
            # If there's no recent refresh or it was more than an hour ago, can_refresh should be True
            # If rate limited, can_refresh should be False and rate_limit_message should be set
            if data['can_refresh'] is False:
                assert data['rate_limit_message'] is not None, \
                    "rate_limit_message should be set when can_refresh is False"
            else:
                # When can_refresh is True, rate_limit_message should be None
                assert data['rate_limit_message'] is None, \
                    "rate_limit_message should be None when can_refresh is True"

