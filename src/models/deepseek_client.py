"""Deepseek API client wrapper for cloud-based LLM"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load .env file (not .env.example - that's just a template)
# In production (GitHub Actions, GCP VM), environment variables are injected directly
# so .env file won't exist and load_dotenv() will silently continue
try:
    # Find project root (go up from src/models/ to project root)
    project_root = Path(__file__).parent.parent.parent.resolve()
    load_dotenv(dotenv_path=str(project_root / '.env'))  # Explicitly load from project root
except Exception:
    # If .env file has issues, continue - production uses injected env vars
    pass


class DeepseekClient:
    """Wrapper for Deepseek API integration (OpenAI-compatible)"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Initialize Deepseek client.
        
        Args:
            api_key: Deepseek API key (default: from DEEPSEEK_API_KEY env var)
            model: Model name (default: deepseek-chat)
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Deepseek API key is required. Set DEEPSEEK_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.base_url = "https://api.deepseek.com"
        
        # Lazy-load the OpenAI client
        self._client = None
    
    @property
    def client(self):
        """Lazy-load OpenAI client"""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError(
                    "Please install openai package: pip install openai"
                )
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        return self._client
    
    def _chat_completion(self, prompt: str, temperature: float = 0.3) -> str:
        """
        Make a chat completion request.
        
        Args:
            prompt: User prompt
            temperature: Sampling temperature (0.0-1.0)
            
        Returns:
            Response text
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides concise, accurate responses."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=1024
        )
        return response.choices[0].message.content.strip()
    
    def summarize(self, text: str, max_length: Optional[int] = None) -> str:
        """
        Summarize text.
        
        Args:
            text: Text to summarize
            max_length: Optional maximum length hint for summary
            
        Returns:
            Summary string
        """
        prompt = f"""Please provide a concise summary of the following text. 
Focus on the main points and key information.

Text:
{text}

Summary:"""
        
        if max_length:
            prompt += f"\n\nKeep the summary under {max_length} words."
        
        return self._chat_completion(prompt, temperature=0.3)
    
    def classify_ai_topic(self, title: str, url: str, content: Optional[str] = None) -> Dict[str, Any]:
        """
        Classify whether content is AI-related.
        
        Args:
            title: Article title
            url: Article URL
            content: Optional article content
            
        Returns:
            Dictionary with 'is_ai_related' (bool) and 'confidence' (float 0-1)
        """
        content_preview = content[:500] if content else "No content available"
        
        prompt = f"""Analyze the following article and determine if it is related to Artificial Intelligence, Machine Learning, or AI technology.

Title: {title}
URL: {url}
Content preview: {content_preview}

Respond with ONLY a JSON object in this exact format:
{{"is_ai_related": true/false, "confidence": 0.0-1.0, "reasoning": "brief explanation"}}

JSON:"""
        
        response = self._chat_completion(prompt, temperature=0.1)
        
        # Try to parse JSON from response
        try:
            # Extract JSON if wrapped in markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            result = json.loads(response)
            return {
                "is_ai_related": bool(result.get("is_ai_related", False)),
                "confidence": float(result.get("confidence", 0.0)),
                "reasoning": result.get("reasoning", "")
            }
        except (json.JSONDecodeError, ValueError, KeyError):
            # Fallback: try to infer from response text
            response_lower = response.lower()
            is_ai = any(keyword in response_lower for keyword in [
                "ai-related", "artificial intelligence", "machine learning",
                "ai technology", "true", "yes"
            ])
            return {
                "is_ai_related": is_ai,
                "confidence": 0.5,
                "reasoning": "Could not parse structured response, inferred from text"
            }
    
    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Generate text.
        
        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            
        Returns:
            Generated text
        """
        return self._chat_completion(prompt, temperature=temperature)
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary with sentiment analysis results
        """
        prompt = f"""Analyze the overall sentiment of these Hacker News comments. 
Consider the tone, opinions, and emotional content.

Comments:
{text}

Respond with ONLY a JSON object in this exact format:
{{
    "sentiment": "positive/negative/neutral/mixed",
    "score": 0.0-1.0,
    "details": "brief explanation of the sentiment",
    "topics": ["topic1", "topic2", "topic3"]
}}

Where:
- sentiment: overall sentiment (positive, negative, neutral, or mixed)
- score: sentiment score from 0.0 (very negative) to 1.0 (very positive), with 0.5 being neutral
- details: brief explanation of why this sentiment was detected
- topics: list of main topics being discussed

JSON:"""
        
        response = self._chat_completion(prompt, temperature=0.1)
        
        try:
            # Extract JSON if wrapped in markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            result = json.loads(response)
            return {
                "sentiment": result.get("sentiment", "neutral").lower(),
                "score": float(result.get("score", 0.5)),
                "details": result.get("details", ""),
                "topics": result.get("topics", [])
            }
        except (json.JSONDecodeError, ValueError, KeyError):
            return {
                "sentiment": "neutral",
                "score": 0.5,
                "details": "Could not parse sentiment response",
                "topics": []
            }
