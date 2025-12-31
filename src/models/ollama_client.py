"""Ollama client wrapper for Qwen models"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Try to use the new langchain-ollama package, fallback to deprecated langchain_community
try:
    from langchain_ollama import OllamaLLM as Ollama
except ImportError:
    try:
        from langchain_community.llms import Ollama
        import warnings
        warnings.filterwarnings("ignore", category=DeprecationWarning)
    except ImportError:
        raise ImportError(
            "Please install langchain-ollama: pip install langchain-ollama\n"
            "Or use the deprecated version: pip install langchain-community"
        )

load_dotenv()


class OllamaClient:
    """Wrapper for Ollama LLM integration with support for multiple Qwen models"""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        summarizer_model: Optional[str] = None,
        filter_model: Optional[str] = None,
        general_model: Optional[str] = None
    ):
        """
        Initialize Ollama client with model configurations.
        
        Args:
            base_url: Ollama base URL (default: http://localhost:11434)
            summarizer_model: Model name for summarization tasks
            filter_model: Model name for filtering tasks
            general_model: Model name for general tasks
        """
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        # Model names with fallbacks
        self.summarizer_model = (
            summarizer_model or 
            os.getenv("OLLAMA_SUMMARIZER_MODEL", "qwen2.5:7b")
        )
        self.filter_model = (
            filter_model or 
            os.getenv("OLLAMA_FILTER_MODEL", "qwen2.5:7b")
        )
        self.general_model = (
            general_model or 
            os.getenv("OLLAMA_GENERAL_MODEL", "qwen2.5:latest")
        )
        
        # Initialize LLM instances
        self._summarizer_llm = None
        self._filter_llm = None
        self._general_llm = None
    
    def get_summarizer_llm(self) -> Ollama:
        """Get LLM instance for summarization tasks"""
        if self._summarizer_llm is None:
            self._summarizer_llm = Ollama(
                base_url=self.base_url,
                model=self.summarizer_model,
                temperature=0.3,
            )
        return self._summarizer_llm
    
    def get_filter_llm(self) -> Ollama:
        """Get LLM instance for filtering tasks"""
        if self._filter_llm is None:
            self._filter_llm = Ollama(
                base_url=self.base_url,
                model=self.filter_model,
                temperature=0.1,
            )
        return self._filter_llm
    
    def get_general_llm(self) -> Ollama:
        """Get LLM instance for general tasks"""
        if self._general_llm is None:
            self._general_llm = Ollama(
                base_url=self.base_url,
                model=self.general_model,
                temperature=0.7,
            )
        return self._general_llm
    
    def summarize(self, text: str, max_length: Optional[int] = None) -> str:
        """
        Summarize text using the summarizer model.
        
        Args:
            text: Text to summarize
            max_length: Optional maximum length hint for summary
            
        Returns:
            Summary string
        """
        llm = self.get_summarizer_llm()
        
        prompt = f"""Please provide a concise summary of the following text. 
Focus on the main points and key information.

Text:
{text}

Summary:"""
        
        if max_length:
            prompt += f"\n\nKeep the summary under {max_length} words."
        
        return llm.invoke(prompt).strip()
    
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
        llm = self.get_filter_llm()
        
        content_preview = content[:500] if content else "No content available"
        
        prompt = f"""Analyze the following article and determine if it is related to Artificial Intelligence, Machine Learning, or AI technology.

Title: {title}
URL: {url}
Content preview: {content_preview}

Respond with ONLY a JSON object in this exact format:
{{"is_ai_related": true/false, "confidence": 0.0-1.0, "reasoning": "brief explanation"}}

JSON:"""
        
        response = llm.invoke(prompt).strip()
        
        # Try to parse JSON from response
        try:
            import json
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
    
    def generate(self, prompt: str, model_type: str = "general") -> str:
        """
        Generate text using specified model type.
        
        Args:
            prompt: Input prompt
            model_type: One of 'summarizer', 'filter', or 'general'
            
        Returns:
            Generated text
        """
        if model_type == "summarizer":
            llm = self.get_summarizer_llm()
        elif model_type == "filter":
            llm = self.get_filter_llm()
        else:
            llm = self.get_general_llm()
        
        return llm.invoke(prompt).strip()

