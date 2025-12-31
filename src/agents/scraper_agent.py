"""Hacker News scraper agent"""

import logging
import re
import time
import requests
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class ScraperAgent:
    """Scrapes Hacker News articles and comments"""
    
    BASE_URL = "https://news.ycombinator.com"
    DEFAULT_TIMEOUT = 10  # seconds
    DEFAULT_DELAY = 1.0  # seconds between requests
    MAX_CONTENT_LENGTH = 5000  # characters
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    def __init__(self, delay: float = None, timeout: int = None):
        """
        Initialize scraper agent.
        
        Args:
            delay: Delay between requests in seconds (to be respectful)
            timeout: Request timeout in seconds
        """
        self.delay = delay if delay is not None else self.DEFAULT_DELAY
        self.timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
    
    def fetch_top_articles(self, top_n: int = 3) -> List[Dict]:
        """
        Fetch top N articles from Hacker News front page.
        
        Args:
            top_n: Number of top articles to fetch
            
        Returns:
            List of article dictionaries with title, url, points, author, time, comment_count
        """
        try:
            response = self.session.get(self.BASE_URL, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            
            articles = []
            rows = soup.find_all("tr", class_="athing")
            
            for idx, row in enumerate(rows[:top_n]):
                try:
                    article = self._parse_article_row(row, soup, idx)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.warning("Error parsing article %d: %s", idx + 1, e)
                    continue
                
                time.sleep(self.delay)
            
            return articles
            
        except requests.RequestException as e:
            logger.error("Error fetching Hacker News: %s", e)
            return []
    
    def _parse_article_row(self, row: BeautifulSoup, soup: BeautifulSoup, idx: int) -> Optional[Dict]:
        """Parse a single article row from HN"""
        try:
            # Get title and URL
            title_elem = row.find("span", class_="titleline")
            if not title_elem:
                return None
            
            link = title_elem.find("a")
            if not link:
                return None
            
            title = link.get_text(strip=True)
            url = link.get("href", "")
            
            # Make absolute URL if relative
            if url and not url.startswith("http"):
                if url.startswith("item?id="):
                    url = urljoin(self.BASE_URL, url)
                else:
                    url = urljoin(self.BASE_URL, url)
            
            # Get metadata from next row
            article_id = row.get("id")
            metadata_row = soup.find("tr", id=f"score_{article_id}")
            if not metadata_row:
                # Try alternative method
                next_row = row.find_next_sibling("tr")
                if next_row:
                    metadata_row = next_row
            
            points = 0
            author = ""
            time_ago = ""
            comment_count = 0
            comment_url = ""
            
            if metadata_row:
                # Extract points
                score_elem = metadata_row.find("span", class_="score")
                if score_elem:
                    points_text = score_elem.get_text(strip=True)
                    points_match = re.search(r"(\d+)", points_text)
                    if points_match:
                        points = int(points_match.group(1))
                
                # Extract author
                author_elem = metadata_row.find("a", class_="hnuser")
                if author_elem:
                    author = author_elem.get_text(strip=True)
                
                # Extract time
                time_elem = metadata_row.find("span", class_="age")
                if time_elem:
                    time_ago = time_elem.get("title", time_elem.get_text(strip=True))
                
                # Extract comment count and URL
                comment_links = metadata_row.find_all("a", href=re.compile(r"item\?id=\d+"))
                for link in comment_links:
                    text = link.get_text(strip=True)
                    if "comment" in text.lower() or "discuss" in text.lower():
                        comment_count_match = re.search(r"(\d+)", text)
                        if comment_count_match:
                            comment_count = int(comment_count_match.group(1))
                        comment_url = urljoin(self.BASE_URL, link.get("href", ""))
                        break
            
            return {
                "id": article_id,
                "rank": idx + 1,
                "title": title,
                "url": url,
                "points": points,
                "author": author,
                "time": time_ago,
                "comment_count": comment_count,
                "comment_url": comment_url
            }
            
        except Exception as e:
            print(f"Error parsing article row: {e}")
            return None
    
    def fetch_comments(self, comment_url: str) -> List[Dict]:
        """
        Fetch comments for an article.
        
        Args:
            comment_url: URL to the article's comment page
            
        Returns:
            List of comment dictionaries
        """
        if not comment_url:
            return []
        
        try:
            time.sleep(self.delay)
            response = self.session.get(comment_url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            
            comments = []
            # HN comments are in table rows with class "athing" and numeric IDs
            # Find all comment rows (they have class "athing" and numeric IDs)
            comment_rows = soup.find_all("tr", class_="athing", id=re.compile(r"^\d+$"))
            
            if not comment_rows:
                # Try alternative: look for any tr with athing class
                comment_rows = soup.find_all("tr", class_="athing")
            
            # Only show summary, not detailed debug info
            
            for row in comment_rows:
                try:
                    comment = self._parse_comment_row(row, soup)
                    if comment and comment.get("text") and len(comment.get("text", "")) >= 15:
                        comments.append(comment)
                except Exception as e:
                    # Silently skip parsing errors
                    continue
            
            if len(comments) > 0:
                logger.info("  ✓ Parsed %d comments", len(comments))
            else:
                logger.warning("  ⚠️  No comments found")
            
            return comments
            
        except requests.RequestException as e:
            logger.warning("  ⚠️  Error fetching comments from %s: %s", comment_url, e)
            return []
        except Exception as e:
            logger.warning("  ⚠️  Unexpected error parsing comments: %s", e)
            return []
    
    def _parse_comment_row(self, row: BeautifulSoup, soup: BeautifulSoup) -> Optional[Dict]:
        """Parse a single comment row"""
        try:
            comment_id = row.get("id")
            if not comment_id:
                return None
            
            # HN comments structure:
            # <tr class="athing" id="12345678">
            #   <td class="ind"><img width="0" ...></td>  <!-- indent -->
            #   <td class="default">
            #     <div style="margin-top:2px; margin-bottom:-10px;">
            #       <span class="commtext c00">Comment text here</span>
            #     </div>
            #   </td>
            # </tr>
            # <tr>
            #   <td></td>
            #   <td class="default">
            #     <span class="age">...</span>
            #     <a class="hnuser">author</a>
            #   </td>
            # </tr>
            
            # Get indentation level (nesting depth) from first row
            indent_elem = row.find("td", class_="ind")
            indent_level = 0
            if indent_elem:
                img = indent_elem.find("img")
                if img and img.get("width"):
                    try:
                        indent_level = int(img.get("width")) // 40  # Each level is ~40px
                    except ValueError:
                        pass
            
            # Get comment text - it's in a DIV with class containing "commtext"
            # HN uses classes like "commtext c00", "commtext c5a", etc.
            # The comment text is in a div.commtext, which can contain p tags with further text
            comment_elem = None
            
            # Helper function to check if a class list contains "commtext"
            def has_commtext_class(class_list):
                if not class_list:
                    return False
                # class_list can be a list or a string
                if isinstance(class_list, list):
                    return any("commtext" in str(c).lower() for c in class_list)
                return "commtext" in str(class_list).lower()
            
            # Method 1: Look for div with commtext class (PRIMARY METHOD)
            # The comment text is in a div, not a span!
            default_td = row.find("td", class_="default")
            if default_td:
                # Find divs with commtext class
                all_divs = default_td.find_all("div")
                for div in all_divs:
                    div_classes = div.get("class", [])
                    if has_commtext_class(div_classes):
                        comment_elem = div
                        break
            
            # Method 2: Use CSS selector to find div with commtext
            if not comment_elem:
                try:
                    commtext_divs = row.select("div[class*='commtext']")
                    if commtext_divs:
                        comment_elem = commtext_divs[0]
                except Exception:
                    pass
            
            # Method 3: Search all divs in current row
            if not comment_elem:
                all_divs = row.find_all("div")
                for div in all_divs:
                    div_classes = div.get("class", [])
                    if has_commtext_class(div_classes):
                        comment_elem = div
                        break
            
            # Method 4: Fallback to span (some comments might use span)
            if not comment_elem:
                all_spans = row.find_all("span")
                for span in all_spans:
                    span_classes = span.get("class", [])
                    if has_commtext_class(span_classes):
                        comment_elem = span
                        break
            
            # Method 5: Look in next sibling row (unlikely but check anyway)
            if not comment_elem:
                next_row = row.find_next_sibling("tr")
                if next_row:
                    default_td = next_row.find("td", class_="default")
                    if default_td:
                        all_divs = default_td.find_all("div")
                        for div in all_divs:
                            div_classes = div.get("class", [])
                            if has_commtext_class(div_classes):
                                comment_elem = div
                                break
            
            if not comment_elem:
                # Skip logging to avoid spam - the outer loop will show debug info
                return None
            
            # Get the actual div/span element (not a copy, so we can modify it)
            # Remove reply links and other noise
            for reply_link in comment_elem.find_all("a", class_="reply"):
                reply_link.decompose()
            
            for link in comment_elem.find_all("a", href=re.compile(r"reply")):
                link.decompose()
            
            for link in comment_elem.find_all("a", href=re.compile(r"flag")):
                link.decompose()
            
            # Get text content - the div can contain p tags with text
            # Use separator to preserve paragraph breaks
            comment_text = comment_elem.get_text(separator="\n", strip=True)
            
            # Clean up: remove excessive newlines but keep paragraph breaks
            comment_text = re.sub(r'\n{3,}', '\n\n', comment_text)
            comment_text = re.sub(r'[ \t]+', ' ', comment_text)  # Normalize spaces
            comment_text = comment_text.strip()
            
            # Skip if comment is too short or empty
            if not comment_text or len(comment_text) < 15:
                return None
            
            # Get author - usually in the next row
            author_elem = None
            next_row = row.find_next_sibling("tr")
            if next_row:
                author_elem = next_row.find("a", class_="hnuser")
            if not author_elem:
                # Fallback: search in current row
                author_elem = row.find("a", class_="hnuser")
            author = author_elem.get_text(strip=True) if author_elem else "unknown"
            
            # Get time - usually in the next row
            time_elem = None
            if next_row:
                time_elem = next_row.find("span", class_="age")
            if not time_elem:
                time_elem = row.find("span", class_="age")
            time_ago = time_elem.get("title", time_elem.get_text(strip=True)) if time_elem else ""
            
            return {
                "id": comment_id,
                "author": author,
                "text": comment_text,
                "time": time_ago,
                "indent_level": indent_level
            }
            
        except Exception as e:
            # Silently skip parsing errors
            return None
    
    def fetch_article_content(self, url: str) -> Optional[str]:
        """
        Fetch and extract text content from an article URL.
        
        Args:
            url: Article URL
            
        Returns:
            Extracted text content or None
        """
        if not url or url.startswith(self.BASE_URL):
            # Skip HN internal links
            return None
        
        try:
            time.sleep(self.delay)
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()
            
            # Try to find main content
            main_content = (
                soup.find("article") or
                soup.find("main") or
                soup.find("div", class_=re.compile(r"content|article|post", re.I)) or
                soup.find("body")
            )
            
            if main_content:
                text = main_content.get_text(separator="\n", strip=True)
                # Clean up excessive whitespace
                text = re.sub(r"\n\s*\n\s*\n", "\n\n", text)
                return text[:self.MAX_CONTENT_LENGTH]
            
            return None
            
        except requests.RequestException:
            return None
        except Exception as e:
            logger.warning("Error fetching article content from %s: %s", url, e)
            return None
    
    def scrape_articles_with_comments(self, top_n: int = 3) -> List[Dict]:
        """
        Scrape top N articles with their comments.
        
        Args:
            top_n: Number of articles to scrape
            
        Returns:
            List of articles with comments included
        """
        articles = self.fetch_top_articles(top_n)
        
        for article in articles:
            logger.info("Fetching comments for: %s...", article['title'][:50])
            comment_url = article.get("comment_url", "")
            if comment_url:
                comments = self.fetch_comments(comment_url)
                logger.info("  Found %d comments", len(comments))
                article["comments"] = comments
            else:
                logger.debug("  No comment URL found")
                article["comments"] = []
            
            # Optionally fetch article content
            article["content"] = self.fetch_article_content(article.get("url", ""))
        
        return articles

