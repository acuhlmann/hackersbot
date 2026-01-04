#!/usr/bin/env python3
"""Quick test script to verify the web server works correctly."""

import urllib.request
import urllib.error
import json
import sys
from pathlib import Path

BASE_URL = "http://localhost:8080"

def test_endpoint(path, expected_status=200, description=""):
    """Test an endpoint and return True if successful."""
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            status = response.getcode()
            content_type = response.headers.get('Content-Type', '')
            content = response.read()
            
            print(f"[OK] {path}")
            print(f"  Status: {status}")
            print(f"  Content-Type: {content_type}")
            print(f"  Content length: {len(content)} bytes")
            
            if description:
                print(f"  {description}")
            
            if status != expected_status:
                print(f"  [FAIL] Expected status {expected_status}, got {status}")
                return False
            
            # Check if it's HTML and contains expected content
            if 'text/html' in content_type:
                content_str = content.decode('utf-8', errors='ignore')
                if 'hackersbot' not in content_str.lower() and path == '/':
                    print(f"  [WARN] HTML doesn't contain 'hackersbot'")
                    print(f"  First 200 chars: {content_str[:200]}")
                    return False
                print(f"  [OK] Contains expected HTML content")
            
            # Check if it's JSON
            if 'application/json' in content_type or path.endswith('.json'):
                try:
                    data = json.loads(content.decode('utf-8'))
                    print(f"  [OK] Valid JSON")
                    if isinstance(data, list):
                        print(f"  [OK] Found {len(data)} items")
                except json.JSONDecodeError:
                    print(f"  [FAIL] Invalid JSON")
                    return False
            
            print()
            return True
            
    except urllib.error.HTTPError as e:
        print(f"[FAIL] {path}")
        print(f"  HTTP Error: {e.code} {e.reason}")
        print()
        return False
    except Exception as e:
        print(f"[FAIL] {path}")
        print(f"  Error: {e}")
        print()
        return False

def main():
    print("Testing HackersBot Web Server")
    print("=" * 50)
    print()
    
    tests = [
        ("/", 200, "Root path should serve index.html"),
        ("/index.html", 200, "Index.html path should work"),
        ("/summaries/index.json", 200, "Summaries index should be accessible"),
        ("/summaries/2026-01-04_08-12-28_summary.json", 200, "Individual summary should be accessible"),
        ("/nonexistent", 404, "Non-existent path should return 404"),
    ]
    
    results = []
    for path, expected_status, description in tests:
        result = test_endpoint(path, expected_status, description)
        results.append((path, result))
    
    print("=" * 50)
    print("Test Results:")
    print()
    
    all_passed = True
    for path, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {path}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("[OK] All tests passed!")
        return 0
    else:
        print("[FAIL] Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())

