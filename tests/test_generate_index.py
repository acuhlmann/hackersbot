"""Tests for the generate_index.py functionality."""

import pytest
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime, timezone

# Import the module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "web"))
from generate_index import generate_index


class TestGenerateIndex:
    """Test the generate_index functionality."""
    
    def test_generate_index_creates_index_file(self, tmp_path):
        """Test that generate_index creates an index.json file."""
        summaries_dir = tmp_path / "summaries"
        summaries_dir.mkdir()
        
        # Create a sample summary file
        sample_summary = {
            "metadata": {"articles_count": 5},
            "articles": [
                {"rank": 1, "title": "Article 1"},
                {"rank": 2, "title": "Article 2"}
            ],
            "generated_at": "2026-01-05T10:00:00"
        }
        
        summary_file = summaries_dir / "2026-01-05_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(sample_summary, f)
        
        # Run generate_index
        result = generate_index(tmp_path)
        
        # Verify index.json was created
        index_file = summaries_dir / "index.json"
        assert index_file.exists(), "index.json should be created"
        
        # Verify content
        with open(index_file, 'r') as f:
            index_data = json.load(f)
        
        assert len(index_data) == 1, "Should have 1 summary"
        assert index_data[0]["timestamp"] == "2026-01-05"
        assert index_data[0]["jsonFile"] == "2026-01-05_summary.json"
        assert index_data[0]["articlesCount"] == 2, "Should count actual articles"
        assert index_data[0]["generatedAt"] == "2026-01-05T10:00:00"
    
    def test_generate_index_counts_articles_correctly(self, tmp_path):
        """Test that generate_index counts articles from the articles array, not metadata."""
        summaries_dir = tmp_path / "summaries"
        summaries_dir.mkdir()
        
        # Create a summary with mismatched metadata and actual articles
        sample_summary = {
            "metadata": {"articles_count": 10},  # Metadata claims 10
            "articles": [
                {"rank": 1, "title": "Article 1"},
                {"rank": 2, "title": "Article 2"},
                {"rank": 3, "title": "Article 3"},
                {"rank": 4, "title": "Article 4"},
                {"rank": 5, "title": "Article 5"}
            ],  # But only 5 articles exist
            "generated_at": "2026-01-05T10:00:00"
        }
        
        summary_file = summaries_dir / "2026-01-05_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(sample_summary, f)
        
        result = generate_index(tmp_path)
        
        # Verify articlesCount matches actual articles, not metadata
        assert result[0]["articlesCount"] == 5, \
            "Should count actual articles (5), not metadata articles_count (10)"
    
    def test_generate_index_counts_ai_articles(self, tmp_path):
        """Test that generate_index correctly counts AI-related articles."""
        summaries_dir = tmp_path / "summaries"
        summaries_dir.mkdir()
        
        sample_summary = {
            "metadata": {},
            "articles": [
                {
                    "rank": 1, 
                    "title": "AI Article",
                    "ai_classification": {"is_ai_related": True, "confidence": 0.9}
                },
                {
                    "rank": 2, 
                    "title": "Non-AI Article",
                    "ai_classification": {"is_ai_related": False, "confidence": 0.1}
                },
                {
                    "rank": 3, 
                    "title": "Low Confidence AI",
                    "ai_classification": {"is_ai_related": True, "confidence": 0.3}  # Below 0.5 threshold
                },
                {
                    "rank": 4, 
                    "title": "High Confidence AI",
                    "ai_classification": {"is_ai_related": True, "confidence": 0.8}
                },
                {
                    "rank": 5, 
                    "title": "No Classification"
                }
            ],
            "generated_at": "2026-01-05T10:00:00"
        }
        
        summary_file = summaries_dir / "2026-01-05_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(sample_summary, f)
        
        result = generate_index(tmp_path)
        
        # Should count only articles with is_ai_related=True AND confidence >= 0.5
        # That's Article 1 (0.9) and Article 4 (0.8) = 2 articles
        assert result[0]["aiArticlesCount"] == 2, \
            "Should count only AI articles with confidence >= 0.5"
    
    def test_generate_index_extracts_generated_at(self, tmp_path):
        """Test that generate_index extracts the generated_at timestamp."""
        summaries_dir = tmp_path / "summaries"
        summaries_dir.mkdir()
        
        timestamp = "2026-01-05T14:30:00.123456"
        sample_summary = {
            "metadata": {},
            "articles": [{"rank": 1, "title": "Test"}],
            "generated_at": timestamp
        }
        
        summary_file = summaries_dir / "2026-01-05_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(sample_summary, f)
        
        result = generate_index(tmp_path)
        
        assert result[0]["generatedAt"] == timestamp, \
            "Should extract generated_at timestamp correctly"
    
    def test_generate_index_handles_missing_generated_at(self, tmp_path):
        """Test that generate_index handles missing generated_at gracefully."""
        summaries_dir = tmp_path / "summaries"
        summaries_dir.mkdir()
        
        sample_summary = {
            "metadata": {},
            "articles": [{"rank": 1, "title": "Test"}]
            # No generated_at field
        }
        
        summary_file = summaries_dir / "2026-01-05_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(sample_summary, f)
        
        result = generate_index(tmp_path)
        
        assert result[0]["generatedAt"] is None, \
            "Should return None when generated_at is missing"
    
    def test_generate_index_handles_empty_summaries_dir(self, tmp_path):
        """Test that generate_index handles empty summaries directory."""
        summaries_dir = tmp_path / "summaries"
        summaries_dir.mkdir()
        
        result = generate_index(tmp_path)
        
        # Verify empty index.json was created
        index_file = summaries_dir / "index.json"
        assert index_file.exists(), "index.json should be created even if empty"
        
        with open(index_file, 'r') as f:
            index_data = json.load(f)
        
        assert index_data == [], "Should return empty list"
    
    def test_generate_index_handles_corrupt_json(self, tmp_path):
        """Test that generate_index handles corrupt JSON files gracefully."""
        summaries_dir = tmp_path / "summaries"
        summaries_dir.mkdir()
        
        # Create a corrupt JSON file
        corrupt_file = summaries_dir / "2026-01-05_summary.json"
        with open(corrupt_file, 'w') as f:
            f.write("{ corrupt json }")
        
        # Should not raise an exception
        result = generate_index(tmp_path)
        
        # Should still create an entry, just with default values
        assert len(result) == 1
        assert result[0]["articlesCount"] == 0
        assert result[0]["aiArticlesCount"] == 0
        assert result[0]["generatedAt"] is None
    
    def test_generate_index_sorts_by_timestamp_descending(self, tmp_path):
        """Test that summaries are sorted by timestamp (newest first)."""
        summaries_dir = tmp_path / "summaries"
        summaries_dir.mkdir()
        
        # Create summaries in non-chronological order
        for date in ["2026-01-01", "2026-01-03", "2026-01-02"]:
            summary = {"metadata": {}, "articles": []}
            summary_file = summaries_dir / f"{date}_summary.json"
            with open(summary_file, 'w') as f:
                json.dump(summary, f)
        
        result = generate_index(tmp_path)
        
        # Should be sorted by timestamp descending (newest first)
        timestamps = [entry["timestamp"] for entry in result]
        assert timestamps == ["2026-01-03", "2026-01-02", "2026-01-01"], \
            "Summaries should be sorted newest first"
