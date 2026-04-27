import os
from dataclasses import dataclass
from typing import Optional
import openai
import anthropic

MODELS = {
    "gpt-4o": {
        "provider": "openai",
        "label": "GPT-4o",
        "description": "OpenAI's most capable model",
    },
    "gpt-4o-mini": {
        "provider": "openai",
        "label": "GPT-4o Mini",
        "description": "Fast and cost-efficient OpenAI model",
    },
    "claude-sonnet-4-6": {
        "provider": "anthropic",
        "label": "Claude Sonnet 4.6",
        "description": "Anthropic's latest balanced model",
    },
    "claude-haiku-4-5-20251001": {
        "provider": "anthropic",
        "label": "Claude Haiku 4.5",
        "description": "Anthropic's fastest model",
    },
    "grok-3": {
        "provider": "grok",
        "label": "Grok 3",
        "description": "xAI's flagship model",
    },
    "grok-3-mini": {
        "provider": "grok",
        "label": "Grok 3 Mini",
        "description": "xAI's efficient model",
    },
}


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def _get_openai_client() -> openai.OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    return openai.OpenAI(api_key=api_key)


def _get_anthropic_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=api_key)


def _get_grok_client() -> openai.OpenAI:
    api_key = os.getenv("GROK_API_KEY")
    if not api_key:
        raise ValueError("GROK_API_KEY not set")
    return openai.OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")


def call_llm(
    model_id: str,
    messages: list[dict],
    system_prompt: Optional[str] = None,
    max_tokens: int = 2048,
) -> LLMResponse:
    if model_id not in MODELS:
        raise ValueError(f"Unknown model: {model_id}")

    provider = MODELS[model_id]["provider"]

    if provider == "openai":
        return _call_openai(_get_openai_client(), model_id, messages, system_prompt, max_tokens)
    elif provider == "anthropic":
        return _call_anthropic(_get_anthropic_client(), model_id, messages, system_prompt, max_tokens)
    elif provider == "grok":
        return _call_openai(_get_grok_client(), model_id, messages, system_prompt, max_tokens)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def _call_openai(
    client: openai.OpenAI,
    model_id: str,
    messages: list[dict],
    system_prompt: Optional[str],
    max_tokens: int,
) -> LLMResponse:
    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    response = client.chat.completions.create(
        model=model_id,
        messages=full_messages,
        max_tokens=max_tokens,
    )
    return LLMResponse(
        content=response.choices[0].message.content,
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )


def _call_anthropic(
    client: anthropic.Anthropic,
    model_id: str,
    messages: list[dict],
    system_prompt: Optional[str],
    max_tokens: int,
) -> LLMResponse:
    kwargs = {"model": model_id, "messages": messages, "max_tokens": max_tokens}
    if system_prompt:
        kwargs["system"] = system_prompt

    response = client.messages.create(**kwargs)
    return LLMResponse(
        content=response.content[0].text,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


def get_available_models(check_keys: bool = True) -> list[dict]:
    result = []
    for model_id, info in MODELS.items():
        provider = info["provider"]
        available = True
        if check_keys:
            key_map = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "grok": "GROK_API_KEY",
            }
            available = bool(os.getenv(key_map.get(provider, "")))
        result.append({
            "id": model_id,
            "label": info["label"],
            "description": info["description"],
            "provider": provider,
            "available": available,
        })
    return result
