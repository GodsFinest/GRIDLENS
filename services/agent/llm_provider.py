"""LLM Provider abstraction supporting Groq, OpenAI, and dynamic grounding-based Mock Provider."""
import os
from abc import ABC, abstractmethod
from typing import Optional, List


class LLMProvider(ABC):
    """Abstract interface for LLM synthesis and formatting."""

    @abstractmethod
    async def generate_response(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        pass


class MockLLMProvider(LLMProvider):
    """
    Deterministic dynamic mock LLM provider.
    Never emits static hardcoded numbers; dynamically synthesizes prose purely by formatting
    the grounding ledger facts and supported inferences supplied in user_prompt.
    """

    async def generate_response(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        # Extract lines from user_prompt
        lines = [line.strip() for line in user_prompt.splitlines() if line.strip()]

        # Identify sections from user prompt
        facts: List[str] = []
        inferences: List[str] = []
        recommendations: List[str] = []
        current_section = None
        for line in lines:
            upper = line.upper()
            if "TOP HYPOTHESIS:" in upper:
                continue
            elif "VERIFIED FACTS:" in upper:
                current_section = "facts"
            elif "SUPPORTED INFERENCES:" in upper:
                current_section = "inferences"
            elif "RECOMMENDATIONS:" in upper:
                current_section = "recommendations"
            elif line.startswith("-") or line.startswith("*"):
                # Remove only our list marker, not Markdown belonging to a quote.
                content = line[2:] if line[:2] in {"- ", "* "} else line[1:]
                if current_section == "facts":
                    facts.append(content)
                elif current_section == "inferences":
                    inferences.append(content)
                elif current_section == "recommendations":
                    recommendations.append(content)

        paragraphs = []
        for title, statements in (("VERIFIED FACTS:", facts), ("SUPPORTED INFERENCES:", inferences),
                                  ("RECOMMENDATIONS:", recommendations)):
            if statements:
                paragraphs.append(title + "\n" + "\n".join("- " + f for f in statements))
        return "\n\n".join(paragraphs)


class GroqLLMProvider(LLMProvider):
    """Groq API provider using httpx (e.g., llama-3.3-70b-versatile)."""

    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model or "llama-3.3-70b-versatile"

    async def generate_response(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        if not self.api_key:
            raise RuntimeError("Live provider unavailable; no mock substitution")

        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": temperature,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception:
            raise RuntimeError("Live provider unavailable; no mock substitution")


class OpenAILLMProvider(LLMProvider):
    """OpenAI API provider using httpx."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or "gpt-4o"

    async def generate_response(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        if not self.api_key:
            raise RuntimeError("Live provider unavailable; no mock substitution")

        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": temperature,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception:
            raise RuntimeError("Live provider unavailable; no mock substitution")


def get_configured_llm_provider() -> LLMProvider:
    provider_name = os.getenv("LLM_PROVIDER", os.getenv("MODEL_PROVIDER", "mock")).lower()
    model_name = os.getenv("LLM_MODEL", "")
    groq_key = os.getenv("GROQ_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")

    if provider_name == "groq" and groq_key:
        return GroqLLMProvider(api_key=groq_key, model=model_name or "llama-3.3-70b-versatile")
    elif provider_name == "openai" and openai_key:
        return OpenAILLMProvider(api_key=openai_key, model=model_name or "gpt-4o")

    return MockLLMProvider()
