"""
LLM Client Module
Handles communication with LLM APIs (Ollama or OpenAI-compatible)
"""

import asyncio
import os
import time
import aiohttp
import json
from typing import Dict, Any, List


class LLMClient:
    def __init__(self, 
                 base_url: str = "http://localhost:11434",
                 model: str = "phi3:mini",
                 api_type: str = "ollama"):
        """
        Initialize LLM client
        
        Args:
            base_url: Base URL for the LLM API
            model: Model name to use
            api_type: Type of API ("ollama" or "openai")
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_type = api_type
        self.session = None
        self.request_logs: List[Dict[str, Any]] = []
    
    async def _ensure_session(self):
        """Ensure aiohttp session exists"""
        if self.session is None:
            headers = {}
            if self.api_type == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                headers.setdefault("Content-Type", "application/json")
                headers.setdefault("Accept", "application/json")
            self.session = aiohttp.ClientSession(headers=headers or None)
    
    async def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """
        Generate text from LLM
        
        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text
        """
        await self._ensure_session()

        start_time = time.perf_counter()
        response_text = ""
        log_entry: Dict[str, Any] = {
            "api_type": self.api_type,
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "success": False,
        }

        try:
            if self.api_type == "ollama":
                response_text = await self._generate_ollama(prompt, temperature)
            elif self.api_type == "openai":
                response_text = await self._generate_openai(prompt, temperature, max_tokens)
            else:
                raise ValueError(f"Unsupported API type: {self.api_type}")

            log_entry["success"] = not str(response_text).lower().startswith("error")
            return response_text
        except Exception as e:
            response_text = f"Error generating response: {str(e)}"
            log_entry["success"] = False
            return response_text
        finally:
            log_entry["duration"] = time.perf_counter() - start_time
            log_entry["response_preview"] = str(response_text).strip()[:200]
            self.request_logs.append(log_entry)
    
    async def _generate_ollama(self, prompt: str, temperature: float) -> str:
        """Generate using Ollama API"""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        try:
            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("response", "")
                else:
                    return f"Error: HTTP {response.status}"
        except asyncio.TimeoutError:
            return "Error: Request timed out"
        except Exception as e:
            return f"Error: {str(e)}"

    async def _generate_openai(self, prompt: str, temperature: float, max_tokens: int) -> str:
        """Generate using OpenAI-compatible API"""

        def _should_use_responses_api(model_name: str) -> bool:
            lowered = model_name.lower()
            prefixes = ("gpt-4.1", "gpt-4o", "gpt-5")
            return any(lowered.startswith(prefix) for prefix in prefixes)

        use_responses_api = _should_use_responses_api(self.model)

        if use_responses_api:
            url = f"{self.base_url}/v1/responses"
            payload = {
                "model": self.model,
                "input": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }
            if _responses_model_disallows_temperature(self.model):
                payload.pop("temperature", None)
        else:
            url = f"{self.base_url}/v1/chat/completions"
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

        try:
            allow_temperature_retry = use_responses_api and "temperature" in payload

            while True:
                async with self.session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    data = await _safe_json(response)

                    if response.status == 200:
                        if use_responses_api:
                            return _extract_from_responses(data)
                        return data["choices"][0]["message"]["content"]

                    error_detail = data.get("error") if isinstance(data, dict) else data

                    if (
                        allow_temperature_retry
                        and _indicates_temperature_unsupported(error_detail)
                    ):
                        _remove_temperature_from_payload(payload)
                        allow_temperature_retry = False
                        continue

                    return f"Error: HTTP {response.status} - {error_detail}"
        except asyncio.TimeoutError:
            return "Error: Request timed out"
        except Exception as e:
            return f"Error: {str(e)}"
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None

    def get_request_logs(self) -> List[Dict[str, Any]]:
        """Return collected request logs"""

        return list(self.request_logs)

    def reset_request_logs(self) -> None:
        """Clear accumulated request logs"""

        self.request_logs.clear()


async def _safe_json(response: aiohttp.ClientResponse) -> Any:
    """Safely deserialize a JSON response body."""

    try:
        return await response.json()
    except Exception:
        try:
            text = await response.text()
        except Exception:
            return {}

        if not text:
            return {}

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text


def _extract_from_responses(payload: Any) -> str:
    """Extract assistant text from the Responses API payload."""

    if not isinstance(payload, dict):
        return str(payload)

    output_blocks = payload.get("output") or []
    collected_text: List[str] = []

    for block in output_blocks:
        if not isinstance(block, dict):
            continue

        contents = block.get("content") or []
        for content in contents:
            if not isinstance(content, dict):
                continue

            if content.get("type") in {"output_text", "text"}:
                text = content.get("text")
                if text:
                    collected_text.append(text)

    if collected_text:
        return "\n".join(collected_text).strip()

    if "output_text" in payload and isinstance(payload["output_text"], list):
        fallback_text = "\n".join(str(item) for item in payload["output_text"] if item)
        if fallback_text:
            return fallback_text.strip()

    return str(payload)


def _indicates_temperature_unsupported(error_detail: Any) -> bool:
    """Return True when the error payload reports that temperature isn't allowed."""

    if not isinstance(error_detail, dict):
        return False

    message = str(error_detail.get("message", "")).lower()
    param = str(error_detail.get("param", "")).lower()

    if "temperature" in param:
        return True

    if "temperature" in message and "unsupported" in message:
        return True

    return False


def _responses_model_disallows_temperature(model_name: str) -> bool:
    """Detect responses models that reject the temperature parameter outright."""

    lowered = model_name.lower()
    disallowed_prefixes = ("gpt-5",)
    return lowered.startswith(disallowed_prefixes)


def _remove_temperature_from_payload(payload: Dict[str, Any]) -> None:
    """Strip temperature fields from the outgoing payload in-place."""

    if not isinstance(payload, dict):
        return

    payload.pop("temperature", None)

    inference_config = payload.get("inference_config")
    if isinstance(inference_config, dict):
        inference_config.pop("temperature", None)
        if not inference_config:
            payload.pop("inference_config", None)
