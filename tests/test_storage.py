"""Tests for the storage module"""

import pytest
import json
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

from src.utils.storage import Storage


class TestStorage:
    """Tests for Storage class"""
    
    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary directory for test outputs"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup after test
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def storage(self, temp_output_dir):
        """Create Storage instance with temporary directory"""
        return Storage(output_dir=temp_output_dir)
    
    def test_storage_creates_output_dir(self, temp_output_dir):
        """Test that storage creates output directory if it doesn't exist"""
        new_dir = os.path.join(temp_output_dir, "new_outputs")
        assert not os.path.exists(new_dir)
        
        storage = Storage(output_dir=new_dir)
        assert os.path.exists(new_dir)
    
    def test_get_timestamp_format(self, storage):
        """Test timestamp format is correct"""
        timestamp = storage.get_timestamp()
        
        # Verify format matches YYYY-MM-DD_HH-MM-SS
        assert len(timestamp) == 19
        parts = timestamp.split("_")
        assert len(parts) == 2
        
        date_parts = parts[0].split("-")
        assert len(date_parts) == 3
        assert len(date_parts[0]) == 4  # Year
        
        time_parts = parts[1].split("-")
        assert len(time_parts) == 3
    
    def test_save_json(self, storage, temp_output_dir):
        """Test saving JSON data"""
        data = {"test": "data", "number": 42}
        filepath = storage.save_json(data, add_generated_at=False)
        
        assert os.path.exists(filepath)
        assert filepath.endswith(".json")
        
        # Verify content
        with open(filepath, "r") as f:
            loaded = json.load(f)
        assert loaded == data
    
    def test_save_json_with_custom_prefix(self, storage):
        """Test saving JSON with custom filename prefix"""
        data = {"test": "data"}
        filepath = storage.save_json(data, filename_prefix="custom")
        
        assert "custom.json" in filepath
    
    def test_save_json_unicode(self, storage, temp_output_dir):
        """Test saving JSON with unicode characters"""
        data = {"emoji": "🤖", "text": "日本語テスト"}
        filepath = storage.save_json(data)
        
        with open(filepath, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["emoji"] == "🤖"
        assert loaded["text"] == "日本語テスト"
    
    def test_save_markdown(self, storage, temp_output_dir):
        """Test saving markdown content"""
        content = "# Test Header\n\nSome **bold** text."
        filepath = storage.save_markdown(content)
        
        assert os.path.exists(filepath)
        assert filepath.endswith(".md")
        
        with open(filepath, "r") as f:
            loaded = f.read()
        assert loaded == content
    
    def test_save_markdown_with_custom_prefix(self, storage):
        """Test saving markdown with custom filename prefix"""
        content = "# Test"
        filepath = storage.save_markdown(content, filename_prefix="report")
        
        assert "report.md" in filepath
    
    def test_save_summaries_both_formats(self, storage, sample_article):
        """Test saving summaries in both JSON and markdown formats"""
        articles = [sample_article]
        metadata = {"test": True}
        
        saved_files = storage.save_summaries(
            articles,
            metadata=metadata,
            formats=["json", "markdown"]
        )
        
        assert "json" in saved_files
        assert "markdown" in saved_files
        assert os.path.exists(saved_files["json"])
        assert os.path.exists(saved_files["markdown"])
    
    def test_save_summaries_json_only(self, storage, sample_article):
        """Test saving summaries in JSON format only"""
        saved_files = storage.save_summaries(
            [sample_article],
            formats=["json"]
        )
        
        assert "json" in saved_files
        assert "markdown" not in saved_files
    
    def test_save_summaries_markdown_only(self, storage, sample_article):
        """Test saving summaries in markdown format only"""
        saved_files = storage.save_summaries(
            [sample_article],
            formats=["markdown"]
        )
        
        assert "markdown" in saved_files
        assert "json" not in saved_files
    
    def test_save_summaries_includes_timestamp(self, storage, sample_article):
        """Test that saved files include timestamp in data"""
        saved_files = storage.save_summaries([sample_article], formats=["json"])
        
        with open(saved_files["json"], "r") as f:
            data = json.load(f)
        
        assert "timestamp" in data
    
    def test_format_as_markdown_calls_formatter(self, storage, sample_article):
        """Test that _format_as_markdown uses Formatter class"""
        data = {
            "timestamp": "2024-01-15_10-30-00",
            "metadata": {"test": True},
            "articles": [sample_article]
        }
        
        result = storage._format_as_markdown(data)
        
        assert "# HackerNews Summary" in result
        assert sample_article["title"] in result
    
    def test_multiple_saves_unique_filenames(self, storage):
        """Test that rapid saves create unique filenames"""
        data1 = {"test": 1}
        data2 = {"test": 2}
        
        # Use a fixed timestamp mock to ensure different files
        with patch.object(storage, 'get_timestamp') as mock_ts:
            mock_ts.side_effect = ["2024-01-15_10-30-00", "2024-01-15_10-30-01"]
            filepath1 = storage.save_json(data1)
            filepath2 = storage.save_json(data2)
        
        assert filepath1 != filepath2
