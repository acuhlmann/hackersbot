"""Storage utility for saving summaries with timestamps"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path


class Storage:
    """Handles saving summaries to files with timestamps"""
    
    def __init__(self, output_dir: str = "outputs"):
        """
        Initialize storage.
        
        Args:
            output_dir: Directory to save output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def get_timestamp(self) -> str:
        """Get current timestamp in YYYY-MM-DD_HH-MM-SS format"""
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    def save_json(self, data: Dict[str, Any], filename_prefix: str = "summary") -> str:
        """
        Save data as JSON file.
        
        Args:
            data: Data dictionary to save
            filename_prefix: Prefix for filename
            
        Returns:
            Path to saved file
        """
        timestamp = self.get_timestamp()
        filename = f"{timestamp}_{filename_prefix}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return str(filepath)
    
    def save_markdown(self, content: str, filename_prefix: str = "summary") -> str:
        """
        Save content as Markdown file.
        
        Args:
            content: Markdown content string
            filename_prefix: Prefix for filename
            
        Returns:
            Path to saved file
        """
        timestamp = self.get_timestamp()
        filename = f"{timestamp}_{filename_prefix}.md"
        filepath = self.output_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        return str(filepath)
    
    def save_summaries(
        self,
        articles: List[Dict],
        metadata: Optional[Dict] = None,
        formats: List[str] = ["json", "markdown"]
    ) -> Dict[str, str]:
        """
        Save article summaries in specified formats.
        
        Args:
            articles: List of summarized articles
            metadata: Optional metadata to include
            formats: List of formats to save ("json", "markdown")
            
        Returns:
            Dictionary mapping format to filepath
        """
        saved_files = {}
        
        # Prepare data structure
        data = {
            "timestamp": self.get_timestamp(),
            "metadata": metadata or {},
            "articles": articles
        }
        
        if "json" in formats:
            json_path = self.save_json(data)
            saved_files["json"] = json_path
        
        if "markdown" in formats:
            # Format as markdown (will be handled by formatter)
            # For now, create a simple markdown representation
            md_content = self._format_as_markdown(data)
            md_path = self.save_markdown(md_content)
            saved_files["markdown"] = md_path
        
        return saved_files
    
    def _format_as_markdown(self, data: Dict) -> str:
        """Format data as markdown using Formatter"""
        from src.utils.formatters import Formatter
        
        metadata = data.get("metadata", {})
        metadata["generated"] = data.get("timestamp", "")
        
        return Formatter.format_markdown(data.get("articles", []), metadata)

