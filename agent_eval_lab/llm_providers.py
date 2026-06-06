"""LLM provider abstraction layer.

Supports multiple backends: Groq, OpenAI, Anthropic, and local (Ollama).
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Optional, Type

from pydantic import BaseModel

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def get_chat_model(self, temperature: float = 0.2) -> BaseChatModel:
        """Return a LangChain chat model instance."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider's name."""
        pass


class GroqProvider(LLMProvider):
    """Groq API provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")

    def get_chat_model(self, temperature: float = 0.2) -> BaseChatModel:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=self.model,
            temperature=temperature,
            api_key=self.api_key,
        )

    def get_provider_name(self) -> str:
        return "groq"


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")

    def get_chat_model(self, temperature: float = 0.2) -> BaseChatModel:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=self.model,
            temperature=temperature,
            api_key=self.api_key,
        )

    def get_provider_name(self) -> str:
        return "openai"


class AnthropicProvider(LLMProvider):
    """Anthropic API provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    def get_chat_model(self, temperature: float = 0.2) -> BaseChatModel:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=self.model,
            temperature=temperature,
            api_key=self.api_key,
            max_tokens=4096,
        )

    def get_provider_name(self) -> str:
        return "anthropic"


class OllamaProvider(LLMProvider):
    """Local Ollama provider."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.2")

    def get_chat_model(self, temperature: float = 0.2) -> BaseChatModel:
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=self.model,
            temperature=temperature,
            base_url=self.base_url,
        )

    def get_provider_name(self) -> str:
        return "ollama"


def get_provider(
    provider_name: Optional[str] = None,
    **kwargs
) -> LLMProvider:
    """Factory function to get the appropriate provider.

    Args:
        provider_name: One of 'groq', 'openai', 'anthropic', 'ollama'
                      Defaults to LLM_PROVIDER env var or 'groq'
        **kwargs: Additional arguments passed to the provider constructor

    Returns:
        An LLMProvider instance
    """
    provider_name = provider_name or os.getenv("LLM_PROVIDER", "groq").lower()

    providers = {
        "groq": GroqProvider,
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "ollama": OllamaProvider,
    }

    if provider_name not in providers:
        raise ValueError(
            f"Unknown provider: {provider_name}. "
            f"Supported: {', '.join(providers.keys())}"
        )

    return providers[provider_name](**kwargs)


def create_structured_chain(
    prompt: ChatPromptTemplate,
    provider: LLMProvider,
    output_schema: Type[BaseModel],
    temperature: float = 0.2,
) -> RunnableSequence:
    """Create a chain with structured output from a prompt and provider."""
    llm = provider.get_chat_model(temperature=temperature)
    structured_llm = llm.with_structured_output(output_schema)
    return prompt | structured_llm
