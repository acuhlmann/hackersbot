"""Unified LLM client interface - DeepSeek only"""

import os
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env file (not .env.example - that's just a template)
# In production (GitHub Actions, GCP VM), environment variables are injected directly
# so .env file won't exist and load_dotenv() will silently continue
try:
    # Find project root (go up from src/models/ to project root)
    project_root = Path(__file__).parent.parent.parent.resolve()
    load_dotenv(dotenv_path=str(project_root / '.env'))  # Explicitly load from project root
except Exception as e:
    # If .env file has encoding issues, log warning but continue
    # Production environments use injected env vars, so this is fine
    logger.warning(f"Could not load .env file: {e}. Continuing with environment variables.")


class LLMClient:
    """
    LLM client that uses DeepSeek API.
    
    This provides a consistent interface for all LLM operations.
    """
    
    def __init__(
        self,
        event_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
        **kwargs
    ):
        """
        Initialize LLM client with DeepSeek.
        
        Args:
            event_handler: Optional callback for instrumentation events
            **kwargs: Additional arguments passed to the underlying client
        """
        self.provider = "deepseek"
        self._client = None
        self._kwargs = kwargs
        self._event_handler = event_handler
        
        logger.info("Initializing LLM client with DeepSeek")

    def _emit(self, payload: Dict[str, Any]) -> None:
        """Emit an instrumentation event, if configured."""
        if not self._event_handler:
            return
        try:
            self._event_handler(payload)
        except Exception:
            # Never let instrumentation break core logic.
            logger.debug("LLM event handler raised; ignoring", exc_info=True)

    @staticmethod
    def _clip(text: Optional[str], limit: int = 600) -> str:
        if not text:
            return ""
        if len(text) <= limit:
            return text
        return text[:limit] + f"... [truncated, {len(text)} chars]"

    @property
    def client(self):
        """Lazy-load the DeepSeek client"""
        if self._client is None:
            from src.models.deepseek_client import DeepseekClient
            self._client = DeepseekClient(**self._kwargs)
        return self._client

    def summarize(self, text: str, max_length: Optional[int] = None) -> str:
        """
        Summarize text using DeepSeek.
        
        Args:
            text: Text to summarize
            max_length: Optional maximum length hint for summary
            
        Returns:
            Summary string
        """
        started = time.time()
        self._emit(
            {
                "type": "llm_call",
                "provider": self.provider,
                "operation": "summarize",
                "input_excerpt": self._clip(text, 900),
                "max_length": max_length,
            }
        )
        try:
            result = self.client.summarize(text, max_length=max_length)
            elapsed_ms = int((time.time() - started) * 1000)
            self._emit(
                {
                    "type": "llm_result",
                    "provider": self.provider,
                    "operation": "summarize",
                    "elapsed_ms": elapsed_ms,
                    "output_excerpt": self._clip(result, 900),
                }
            )
            return result
        except Exception as e:
            elapsed_ms = int((time.time() - started) * 1000)
            self._emit(
                {
                    "type": "llm_error",
                    "provider": self.provider,
                    "operation": "summarize",
                    "elapsed_ms": elapsed_ms,
                    "error": str(e),
                }
            )
            raise

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
        started = time.time()
        self._emit(
            {
                "type": "llm_call",
                "provider": self.provider,
                "operation": "classify_ai_topic",
                "title": title,
                "url": url,
                "content_excerpt": self._clip(content, 600),
            }
        )
        try:
            result = self.client.classify_ai_topic(title=title, url=url, content=content)
            elapsed_ms = int((time.time() - started) * 1000)
            self._emit(
                {
                    "type": "llm_result",
                    "provider": self.provider,
                    "operation": "classify_ai_topic",
                    "elapsed_ms": elapsed_ms,
                    "result": result,
                }
            )
            return result
        except Exception as e:
            elapsed_ms = int((time.time() - started) * 1000)
            self._emit(
                {
                    "type": "llm_error",
                    "provider": self.provider,
                    "operation": "classify_ai_topic",
                    "elapsed_ms": elapsed_ms,
                    "error": str(e),
                }
            )
            raise

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Generate text using DeepSeek.
        
        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            
        Returns:
            Generated text
        """
        started = time.time()
        self._emit(
            {
                "type": "llm_request",
                "provider": self.provider,
                "role": "generate",
                "temperature": temperature,
                "prompt_excerpt": self._clip(prompt, 900),
            }
        )
        try:
            result = self.client.generate(prompt, temperature=temperature)
            elapsed_ms = int((time.time() - started) * 1000)
            self._emit(
                {
                    "type": "llm_response",
                    "provider": self.provider,
                    "role": "generate",
                    "elapsed_ms": elapsed_ms,
                    "response_excerpt": self._clip(result, 900),
                }
            )
            return result
        except Exception as e:
            elapsed_ms = int((time.time() - started) * 1000)
            self._emit(
                {
                    "type": "llm_error",
                    "provider": self.provider,
                    "role": "generate",
                    "elapsed_ms": elapsed_ms,
                    "error": str(e),
                }
            )
            raise

    def get_filter_llm(self):
        """
        Get the filter LLM.
        Returns self since DeepSeek uses a single client for all operations.
        """
        return self

    def get_summarizer_llm(self):
        """
        Get the summarizer LLM.
        Returns self since DeepSeek uses a single client for all operations.
        """
        return self

    def invoke(self, prompt: str) -> str:
        """
        Invoke the LLM with a prompt (compatibility method for langchain-style calls).
        
        Args:
            prompt: Input prompt
            
        Returns:
            Generated text
        """
        started = time.time()
        self._emit(
            {
                "type": "llm_request",
                "provider": self.provider,
                "role": "invoke",
                "prompt_excerpt": self._clip(prompt, 900),
            }
        )
        try:
            result = self.client.generate(prompt, temperature=0.3)
            result_str = str(result).strip()
            elapsed_ms = int((time.time() - started) * 1000)
            self._emit(
                {
                    "type": "llm_response",
                    "provider": self.provider,
                    "role": "invoke",
                    "elapsed_ms": elapsed_ms,
                    "response_excerpt": self._clip(result_str, 900),
                }
            )
            return result_str
        except Exception as e:
            elapsed_ms = int((time.time() - started) * 1000)
            self._emit(
                {
                    "type": "llm_error",
                    "provider": self.provider,
                    "role": "invoke",
                    "elapsed_ms": elapsed_ms,
                    "error": str(e),
                }
            )
            raise


def get_llm_client(**kwargs) -> LLMClient:
    """
    Factory function to get an LLM client.
    
    Args:
        **kwargs: Additional arguments for the client
        
    Returns:
        Configured LLMClient instance
    """
    # Remove 'provider' kwarg if present (no longer used)
    kwargs.pop('provider', None)
    return LLMClient(**kwargs)
