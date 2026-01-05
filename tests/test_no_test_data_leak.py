"""Regression tests to prevent "test data in production" leaks.

These tests ensure we never ship summaries that look like test fixtures
(e.g. 'Test Article 1' / example.com URLs / llm_provider='test').
"""

from __future__ import annotations

import json
from pathlib import Path


def test_summaries_do_not_contain_obvious_test_fixtures() -> None:
    summaries_dir = Path(__file__).parent.parent / "summaries"
    assert summaries_dir.exists(), "summaries/ directory should exist"

    summary_files = sorted(summaries_dir.glob("*_summary.json"))
    assert summary_files, "Expected at least one summary json in summaries/"

    bad_files: list[str] = []

    for path in summary_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            # If a summary is malformed, that's already a release blocker.
            bad_files.append(f"{path.name} (invalid json)")
            continue

        meta = data.get("metadata") or {}
        if str(meta.get("llm_provider", "")).lower() == "test":
            bad_files.append(f"{path.name} (metadata.llm_provider=test)")
            continue

        articles = data.get("articles") or []
        for a in articles:
            title = str(a.get("title") or "")
            url = str(a.get("url") or "")

            if title.lower().startswith("test article"):
                bad_files.append(f"{path.name} (title='{title}')")
                break
            if "example.com" in url.lower():
                bad_files.append(f"{path.name} (url='{url}')")
                break

    assert not bad_files, "Found test-like summary data: " + ", ".join(bad_files)

