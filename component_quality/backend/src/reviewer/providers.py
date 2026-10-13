import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Type

from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

logger = logging.getLogger(__name__)

class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, model: Optional[str] = None, temperature: float = 0.0, max_tokens: int = 4000):
        self.model = model or os.getenv("LLM_MODEL")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", str(temperature)))
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", str(max_tokens)))

    @abstractmethod
    def generate_structured(self, system_prompt: str, user_prompt: str, response_model: Type[BaseModel]) -> tuple[BaseModel, Dict[str, Any]]:
        """
        Generates a structured response based on the prompts.
        Returns:
            - Parsed Pydantic model instance
            - Usage metadata dict (latency, tokens, etc.)
        """
        pass

class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM implementation supporting structured output via JSON mode."""
    
    def __init__(self, model: Optional[str] = "gpt-4o-mini", temperature: float = 0.0, max_tokens: int = 4000):
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self.api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("No LLM_API_KEY or OPENAI_API_KEY found in environment.")
            
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        except ImportError:
            self.client = None
            logger.error("openai library is not installed. OpenAIProvider will fail.")

    def generate_structured(self, system_prompt: str, user_prompt: str, response_model: Type[BaseModel]) -> tuple[BaseModel, Dict[str, Any]]:
        if not self.client:
            raise RuntimeError("OpenAI provider requires the `openai` Python package.")
            
        import time
        start_time = time.time()
        
        # We append a reminder to return JSON matching the schema
        schema_json = response_model.model_json_schema()
        system_with_schema = f"{system_prompt}\n\nYou MUST return ONLY valid JSON matching this schema:\n{json.dumps(schema_json, indent=2)}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_with_schema},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )
            
            latency = time.time() - start_time
            content = response.choices[0].message.content
            usage = response.usage
            
            # Parse output
            parsed_result = response_model.model_validate_json(content)
            
            metadata = {
                "model": self.model,
                "latency_sec": latency,
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0
            }
            
            return parsed_result, metadata
            
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

def get_llm_provider() -> BaseLLMProvider:
    """Factory to get the configured provider."""
    provider_name = os.getenv("LLM_PROVIDER", "openai").lower()
    
    if provider_name == "openai":
        return OpenAIProvider()
    # Placeholder for AnthropicProvider, GoogleProvider, etc.
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider_name}")
