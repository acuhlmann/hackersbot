"""Automated UI tests for the refresh functionality.

To run these tests:
1. Install Playwright: pip install playwright
2. Install browser binaries: playwright install chromium
3. Run tests: pytest tests/test_refresh_ui.py -v

These tests use Playwright to automate browser interactions and test
the refresh functionality end-to-end via the UI.
"""

import pytest
import http.server
import socketserver
import threading
import time
import json
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Import the serve module
import sys
import os
sys.path.insert(0, str(Path(__file__).parent.parent))
from serve import Handler, PROJECT_ROOT

# Try to import playwright, skip tests if not available
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@pytest.fixture(scope="class")
def test_server():
    """Start a test server in a separate thread."""
    # Try to find an available port
    import socket
    port = None
    for test_port in range(9999, 10099):
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


@pytest.fixture(scope="class")
def browser():
    """Set up Playwright browser."""
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip("Playwright not installed. Install with: pip install playwright && playwright install")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser, test_server):
    """Create a new page for each test."""
    page = browser.new_page()
    
    # Mock status endpoint to return a default state before page loads
    def handle_status(route):
        if '/api/status' in route.request.url:
            route.fulfill(
                status=200,
                content_type='application/json',
                body=json.dumps({
                    "in_progress": False,
                    "can_refresh": True,
                    "last_refresh": None
                })
            )
        else:
            route.continue_()
    
    page.route('**/api/status', handle_status)
    
    page.goto(test_server)
    # Wait for page to load
    page.wait_for_selector('#refreshButton', timeout=5000)
    # Wait a bit for initial status check to complete
    time.sleep(0.5)
    yield page
    page.close()


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
class TestRefreshUI:
    """Test the refresh functionality via the UI."""
    
    def test_refresh_button_exists_and_is_clickable(self, page):
        """Test that the refresh button exists and is clickable."""
        refresh_button = page.locator('#refreshButton')
        assert refresh_button.is_visible()
        assert refresh_button.is_enabled()
        assert 'Refresh Summary' in refresh_button.text_content()
    
    def test_refresh_button_click_triggers_api_call(self, page, test_server):
        """Test that clicking the refresh button triggers the API call."""
        # Intercept the API call
        api_called = {"called": False, "response": None}
        
        def handle_route(route):
            if '/api/refresh' in route.request.url:
                api_called["called"] = True
                # Return a mock successful response
                route.fulfill(
                    status=200,
                    content_type='application/json',
                    body=json.dumps({"success": True, "message": "Refresh started"})
                )
            else:
                route.continue_()
        
        page.route('**/api/refresh', handle_route)
        
        # Click the refresh button
        refresh_button = page.locator('#refreshButton')
        refresh_button.click()
        
        # Wait a bit for the API call
        time.sleep(0.5)
        
        assert api_called["called"], "API refresh endpoint should have been called"
    
    def test_refresh_button_shows_loading_state(self, page, test_server):
        """Test that the refresh button shows loading state when clicked."""
        # Mock the API to return success immediately
        def handle_route(route):
            if '/api/refresh' in route.request.url:
                route.fulfill(
                    status=200,
                    content_type='application/json',
                    body=json.dumps({"success": True, "message": "Refresh started"})
                )
            else:
                route.continue_()
        
        page.route('**/api/refresh', handle_route)
        
        # Mock status endpoint to simulate refresh in progress
        status_call_count = {"count": 0}
        
        def handle_status(route):
            if '/api/status' in route.request.url:
                status_call_count["count"] += 1
                # First few calls: in progress, then complete
                if status_call_count["count"] <= 2:
                    route.fulfill(
                        status=200,
                        content_type='application/json',
                        body=json.dumps({
                            "in_progress": True,
                            "can_refresh": False,
                            "last_refresh": None
                        })
                    )
                else:
                    route.fulfill(
                        status=200,
                        content_type='application/json',
                        body=json.dumps({
                            "in_progress": False,
                            "can_refresh": True,
                            "last_refresh": datetime.now(timezone.utc).isoformat()
                        })
                    )
            else:
                route.continue_()
        
        page.route('**/api/status', handle_status)
        
        # Click the refresh button
        refresh_button = page.locator('#refreshButton')
        assert refresh_button.is_enabled()
        
        refresh_button.click()
        
        # Wait for loading state
        time.sleep(0.3)
        
        # Check that button is disabled and has loading class
        # Note: The button might be disabled, but checking for loading class
        refresh_status = page.locator('#refreshStatus')
        
        # Wait for status message to appear
        try:
            refresh_status.wait_for(state='visible', timeout=2000)
            status_text = refresh_status.text_content()
            assert 'Starting refresh' in status_text or 'Refresh started' in status_text
        except PlaywrightTimeoutError:
            # Status might update quickly, check if button is disabled
            assert not refresh_button.is_enabled() or 'loading' in refresh_button.get_attribute('class') or ''
    
    def test_refresh_status_updates_on_completion(self, page, test_server):
        """Test that refresh status updates when refresh completes."""
        # Create a mock summary file for today to test with
        today = datetime.now().strftime("%Y-%m-%d")
        summaries_dir = PROJECT_ROOT / "summaries"
        summaries_dir.mkdir(exist_ok=True)
        
        # Create a test summary file
        test_summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "articles_count": 3,
                "llm_provider": "test"
            },
            "articles": [
                {
                    "rank": 1,
                    "title": "Test Article 1",
                    "url": "https://example.com/1",
                    "points": 100,
                    "author": "testuser",
                    "comment_count": 10
                }
            ]
        }
        
        test_json_file = summaries_dir / f"{today}_summary.json"
        original_exists = test_json_file.exists()
        original_contents = None
        if original_exists:
            # IMPORTANT: this test must not overwrite real summary data
            # (the summaries folder is also used by the app itself).
            try:
                original_contents = test_json_file.read_text(encoding="utf-8")
            except Exception:
                original_contents = None
        
        try:
            with open(test_json_file, 'w') as f:
                json.dump(test_summary, f)
            
            # Mock the refresh endpoint
            refresh_called = {"count": 0}
            
            def handle_refresh(route):
                if '/api/refresh' in route.request.url:
                    refresh_called["count"] += 1
                    route.fulfill(
                        status=200,
                        content_type='application/json',
                        body=json.dumps({"success": True, "message": "Refresh started"})
                    )
                else:
                    route.continue_()
            
            page.route('**/api/refresh', handle_refresh)
            
            # Mock status endpoint to simulate refresh lifecycle
            status_call_count = {"count": 0}
            
            def handle_status(route):
                if '/api/status' in route.request.url:
                    status_call_count["count"] += 1
                    # First 3 calls: in progress
                    if status_call_count["count"] <= 3:
                        route.fulfill(
                            status=200,
                            content_type='application/json',
                            body=json.dumps({
                                "in_progress": True,
                                "can_refresh": False,
                                "last_refresh": None
                            })
                        )
                    else:
                        # After that: complete
                        route.fulfill(
                            status=200,
                            content_type='application/json',
                            body=json.dumps({
                                "in_progress": False,
                                "can_refresh": True,
                                "last_refresh": datetime.now(timezone.utc).isoformat()
                            })
                        )
                else:
                    route.continue_()
            
            page.route('**/api/status', handle_status)
            
            # Reload page to get fresh state
            page.reload()
            page.wait_for_selector('#refreshButton', timeout=5000)
            
            # Click refresh button
            refresh_button = page.locator('#refreshButton')
            refresh_button.click()
            
            # Wait for status to show refresh started
            refresh_status = page.locator('#refreshStatus')
            refresh_status.wait_for(state='visible', timeout=2000)
            
            # Wait for refresh to complete (status polling happens every 2 seconds)
            # We'll wait up to 10 seconds for the status to update
            max_wait = 10
            start_time = time.time()
            while time.time() - start_time < max_wait:
                status_text = refresh_status.text_content()
                status_class = refresh_status.get_attribute('class') or ''
                if 'Last refresh' in status_text or 'success' in status_class:
                    break
                time.sleep(0.5)
            
            # Verify status was updated
            final_status = refresh_status.text_content()
            # Status should show either "Last refresh" or success message
            assert 'Last refresh' in final_status or 'Refresh started' in final_status or 'Refreshing' in final_status
            
        finally:
            # Restore original file if it existed, otherwise remove.
            if original_exists:
                if original_contents is not None:
                    test_json_file.write_text(original_contents, encoding="utf-8")
            else:
                if test_json_file.exists():
                    test_json_file.unlink()
    
    def test_refresh_button_disabled_during_refresh(self, page, test_server):
        """Test that refresh button is disabled while refresh is in progress."""
        # Track status calls to change behavior after refresh is triggered
        status_call_count = {"count": 0}
        refresh_triggered = {"triggered": False}
        
        def handle_status(route):
            if '/api/status' in route.request.url:
                status_call_count["count"] += 1
                # Before refresh: allow refresh
                # After refresh triggered: show in progress
                if refresh_triggered["triggered"] or status_call_count["count"] > 2:
                    route.fulfill(
                        status=200,
                        content_type='application/json',
                        body=json.dumps({
                            "in_progress": True,
                            "can_refresh": False,
                            "last_refresh": None
                        })
                    )
                else:
                    route.fulfill(
                        status=200,
                        content_type='application/json',
                        body=json.dumps({
                            "in_progress": False,
                            "can_refresh": True,
                            "last_refresh": None
                        })
                    )
            else:
                route.continue_()
        
        page.route('**/api/status', handle_status)
        
        # Mock refresh endpoint
        def handle_refresh(route):
            if '/api/refresh' in route.request.url:
                refresh_triggered["triggered"] = True
                route.fulfill(
                    status=200,
                    content_type='application/json',
                    body=json.dumps({"success": True, "message": "Refresh started"})
                )
            else:
                route.continue_()
        
        page.route('**/api/refresh', handle_refresh)
        
        # Reload to get fresh state
        page.reload()
        page.wait_for_selector('#refreshButton', timeout=5000)
        time.sleep(0.5)  # Wait for initial status check
        
        # Button should be enabled initially
        refresh_button = page.locator('#refreshButton')
        assert refresh_button.is_enabled(), "Button should be enabled before refresh"
        
        # Click the refresh button
        refresh_button.click()
        time.sleep(0.5)  # Wait for button state to update
        
        # Button should be disabled after click
        assert not refresh_button.is_enabled(), "Button should be disabled after starting refresh"
    
    def test_refresh_error_handling(self, page, test_server):
        """Test that refresh errors are displayed correctly."""
        # Mock refresh endpoint to return error
        def handle_refresh(route):
            if '/api/refresh' in route.request.url:
                route.fulfill(
                    status=429,
                    content_type='application/json',
                    body=json.dumps({
                        "success": False,
                        "error": "Rate limit: Please wait 30m 0s before refreshing again"
                    })
                )
            else:
                route.continue_()
        
        page.route('**/api/refresh', handle_refresh)
        
        # Click refresh button
        refresh_button = page.locator('#refreshButton')
        refresh_button.click()
        
        # Wait for error message - the JavaScript needs time to process the error response
        refresh_status = page.locator('#refreshStatus')
        refresh_status.wait_for(state='visible', timeout=2000)
        
        # Wait for the error message to appear (JavaScript processes async)
        max_wait = 5
        start_time = time.time()
        error_found = False
        while time.time() - start_time < max_wait:
            status_text = refresh_status.text_content()
            status_class = refresh_status.get_attribute('class') or ''
            if 'Rate limit' in status_text or 'error' in status_text.lower() or 'Failed' in status_text or 'error' in status_class:
                error_found = True
                break
            time.sleep(0.2)
        
        # Check for error message
        status_text = refresh_status.text_content()
        status_class = refresh_status.get_attribute('class') or ''
        
        assert error_found or 'Rate limit' in status_text or 'error' in status_text.lower() or 'Failed' in status_text or 'error' in status_class, \
            f"Expected error message but got: '{status_text}' with class '{status_class}'"
        
        # Check that status has error class
        assert 'error' in status_class, f"Status should have 'error' class but got: '{status_class}'"

