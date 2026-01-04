#!/usr/bin/env python3
"""Generate index.json for the web UI from available summaries."""

import json
import os
from pathlib import Path


def generate_index(base_dir=None):
    """Scan the summaries folder and create an index.json file."""
    if base_dir is None:
        base_dir = Path(__file__).parent.parent
    else:
        base_dir = Path(base_dir)
    
    summaries_dir = base_dir / "summaries"
    
    summaries = []
    
    # Find all JSON summary files
    for json_file in sorted(summaries_dir.glob("*_summary.json"), reverse=True):
        timestamp = json_file.stem.replace("_summary", "")
        
        # Try to get article count, AI article count, and generated_at from the file
        articles_count = 0
        ai_articles_count = 0
        generated_at = None
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                articles = data.get('articles', [])
                articles_count = len(articles)
                generated_at = data.get('generated_at')
                
                # Count AI-related articles
                for article in articles:
                    classification = article.get('ai_classification', {})
                    if classification.get('is_ai_related') and classification.get('confidence', 0) >= 0.5:
                        ai_articles_count += 1
        except Exception:
            pass
        
        summaries.append({
            "timestamp": timestamp,
            "jsonFile": json_file.name,
            "articlesCount": articles_count,
            "aiArticlesCount": ai_articles_count,
            "generatedAt": generated_at
        })
    
    # Write the index
    index_path = summaries_dir / "index.json"
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(summaries, f, indent=2)
    
    print(f"Generated index.json with {len(summaries)} summaries")
    return summaries


if __name__ == "__main__":
    generate_index()

