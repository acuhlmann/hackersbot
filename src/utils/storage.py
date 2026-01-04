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
    
    def get_date_only(self) -> str:
        """Get current date in YYYY-MM-DD format (for daily summaries)"""
        return datetime.now().strftime("%Y-%m-%d")
    
    def save_json(
        self, 
        data: Dict[str, Any], 
        filename_prefix: str = "summary",
        use_date_only: bool = False
    ) -> str:
        """
        Save data as JSON file.
        
        Args:
            data: Data dictionary to save
            filename_prefix: Prefix for filename
            use_date_only: If True, use date-only filename (one per day, replaces existing)
            
        Returns:
            Path to saved file
        """
        if use_date_only:
            date_str = self.get_date_only()
            filename = f"{date_str}_{filename_prefix}.json"
        else:
            timestamp = self.get_timestamp()
            filename = f"{timestamp}_{filename_prefix}.json"
        
        filepath = self.output_dir / filename
        
        # Add generated_at timestamp to the data
        data_with_timestamp = data.copy()
        data_with_timestamp["generated_at"] = datetime.now().isoformat()
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data_with_timestamp, f, indent=2, ensure_ascii=False)
        
        return str(filepath)
    
    def save_markdown(
        self, 
        content: str, 
        filename_prefix: str = "summary",
        use_date_only: bool = False
    ) -> str:
        """
        Save content as Markdown file.
        
        Args:
            content: Markdown content string
            filename_prefix: Prefix for filename
            use_date_only: If True, use date-only filename (one per day, replaces existing)
            
        Returns:
            Path to saved file
        """
        if use_date_only:
            date_str = self.get_date_only()
            filename = f"{date_str}_{filename_prefix}.md"
        else:
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
        formats: Optional[List[str]] = None
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
        if formats is None:
            formats = ["json", "markdown"]
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

