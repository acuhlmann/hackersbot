"""Unified LLM client interface that supports multiple providers"""

import os
import logging
import urllib.request
import urllib.error
import json
import time
from typing import Optional, Dict, Any, Literal, List, Callable, TypedDict, cast
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Type for provider selection
LLMProvider = Literal["ollama", "deepseek", "auto"]


def check_ollama_available(base_url: str = "http://localhost:11434") -> tuple[bool, List[str]]:
    """
    Check if Ollama is running and has models available.
    
    Args:
        base_url: Ollama API base URL
        
    Returns:
        Tuple of (is_available, list_of_models)
    """
    try:
        # Check if Ollama API is responding
        req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        req.add_header("Content-Type", "application/json")
        
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            models = [m.get("name", "") for m in data.get("models", [])]
            return len(models) > 0, models
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, Exception) as e:
        logger.debug(f"Ollama not available: {e}")
        return False, []


def detect_best_provider() -> LLMProvider:
    """
    Auto-detect the best available LLM provider.
    
    Priority:
    1. If OLLAMA is available locally with models, use it
    2. If DEEPSEEK_API_KEY is set, use deepseek
    3. Fall back to ollama (will error if not available)
    
    Returns:
        The recommended provider name
    """
    # Check for Ollama first (local is preferred)
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_available, models = check_ollama_available(ollama_url)
    
    if ollama_available:
        logger.info(f"Ollama detected with {len(models)} model(s): {', '.join(models[:3])}{'...' if len(models) > 3 else ''}")
        return "ollama"
    
    # Check for Deepseek API key
    if os.getenv("DEEPSEEK_API_KEY"):
        logger.info("Using Deepseek API (DEEPSEEK_API_KEY found)")
        return "deepseek"
    
    # Default to ollama (will show error when used if not available)
    logger.warning("No LLM provider detected. Defaulting to ollama.")
    return "ollama"


class LLMClient:
    """
    Unified LLM client that can use either Ollama (local) or Deepseek (cloud).
    
    This provides a consistent interface regardless of the backend provider.
    """
    
    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        event_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
        **kwargs
    ):
        """
        Initialize LLM client with specified provider.
        
        Args:
            provider: LLM provider ('ollama', 'deepseek', or 'auto'). 
                     Default: 'auto' (auto-detect best available provider)
            **kwargs: Additional arguments passed to the underlying client
        """
        # Get provider from argument, env var, or auto-detect
        requested_provider = provider or os.getenv("LLM_PROVIDER", "auto")
        
        # Auto-detect if requested
        if requested_provider == "auto":
            self.provider = detect_best_provider()
        else:
            self.provider = requested_provider
        
        self._client = None
        self._kwargs = kwargs
        self._event_handler = event_handler
        
        logger.info(f"Initializing LLM client with provider: {self.provider}")

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
        """Lazy-load the appropriate client"""
        if self._client is None:
            if self.provider == "deepseek":
                from src.models.deepseek_client import DeepseekClient
                self._client = DeepseekClient(**self._kwargs)
            else:
                from src.models.ollama_client import OllamaClient
                self._client = OllamaClient(**self._kwargs)
        return self._client

    def summarize(self, text: str, max_length: Optional[int] = None) -> str:
        """
        Summarize text using the configured provider.
        
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
        Generate text using the configured provider.
        
        Args:
            prompt: Input prompt
            temperature: Sampling temperature (for Deepseek; ignored for Ollama which uses model_type)
            
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
            if self.provider == "deepseek":
                result = self.client.generate(prompt, temperature=temperature)
            else:
                # Ollama client uses model_type parameter
                result = self.client.generate(prompt, model_type="general")
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
        Get the filter LLM (for direct access when needed).
        For Ollama, returns the filter-specific LLM.
        For Deepseek, returns self (uses same client).
        """
        if self.provider == "ollama":
            return _InvokeWrapper(
                self.client.get_filter_llm(),
                self._emit,
                provider=self.provider,
                role="filter",
            )
        return self

    def get_summarizer_llm(self):
        """
        Get the summarizer LLM (for direct access when needed).
        For Ollama, returns the summarizer-specific LLM.
        For Deepseek, returns self (uses same client).
        """
        if self.provider == "ollama":
            return _InvokeWrapper(
                self.client.get_summarizer_llm(),
                self._emit,
                provider=self.provider,
                role="summarizer",
            )
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
            if self.provider == "deepseek":
                result = self.client.generate(prompt, temperature=0.3)
            else:
                # For Ollama, use the summarizer LLM
                result = self.client.get_summarizer_llm().invoke(prompt)
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


class _InvokeWrapper:
    """Wraps an object with an .invoke(prompt) method and emits events."""

    def __init__(
        self,
        llm: Any,
        emit: Callable[[Dict[str, Any]], None],
        *,
        provider: str,
        role: str,
    ):
        self._llm = llm
        self._emit = emit
        self._provider = provider
        self._role = role

    def invoke(self, prompt: str) -> str:
        started = time.time()
        self._emit(
            {
                "type": "llm_request",
                "provider": self._provider,
                "role": self._role,
                "prompt_excerpt": LLMClient._clip(prompt, 900),
            }
        )
        try:
            result = self._llm.invoke(prompt)
            result_str = str(result).strip()
            elapsed_ms = int((time.time() - started) * 1000)
            self._emit(
                {
                    "type": "llm_response",
                    "provider": self._provider,
                    "role": self._role,
                    "elapsed_ms": elapsed_ms,
                    "response_excerpt": LLMClient._clip(result_str, 900),
                }
            )
            return result_str
        except Exception as e:
            elapsed_ms = int((time.time() - started) * 1000)
            self._emit(
                {
                    "type": "llm_error",
                    "provider": self._provider,
                    "role": self._role,
                    "elapsed_ms": elapsed_ms,
                    "error": str(e),
                }
            )
            raise

    def __getattr__(self, name: str) -> Any:
        return getattr(self._llm, name)


def get_llm_client(provider: Optional[LLMProvider] = None, **kwargs) -> LLMClient:
    """
    Factory function to get an LLM client.
    
    Args:
        provider: LLM provider ('ollama' or 'deepseek')
        **kwargs: Additional arguments for the client
        
    Returns:
        Configured LLMClient instance
    """
    return LLMClient(provider=provider, **kwargs)
