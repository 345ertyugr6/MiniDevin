"""
LLM Client Module
Handles communication with LLM APIs (Ollama or OpenAI-compatible)
"""

import asyncio
import os
import time
import aiohttp
import json
from typing import Dict, Any, Optional, List


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
            headers = None
            if self.api_type == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    headers = {"Authorization": f"Bearer {api_key}"}
            self.session = aiohttp.ClientSession(headers=headers)
    
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
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            headers = None
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                headers = {"Authorization": f"Bearer {api_key}"}

            async with self.session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    return f"Error: HTTP {response.status}"
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
