import os
from abc import ABC, abstractmethod
import google.generativeai as genai
from openai import OpenAI, AsyncOpenAI
from typing import AsyncGenerator, Generator, Optional
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class LLMProcessor(ABC):
    @abstractmethod
    async def process_text(self, text: str, prompt: str, model: Optional[str] = None) -> AsyncGenerator[str, None]:
        pass
    
    @abstractmethod
    def process_text_sync(self, text: str, prompt: str, model: Optional[str] = None) -> str:
        pass

class GeminiProcessor(LLMProcessor):
    def __init__(self, default_model: str = 'gemini-1.5-pro'):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise EnvironmentError("GOOGLE_API_KEY is not set")
        genai.configure(api_key=api_key)
        self.default_model = default_model

    async def process_text(self, text: str, prompt: str, model: Optional[str] = None) -> AsyncGenerator[str, None]:
        all_prompt = f"{prompt}\n\n{text}"
        model_name = model or self.default_model
        logger.info(f"Using model: {model_name} for processing")
        logger.info(f"Prompt: {all_prompt}")
        genai_model = genai.GenerativeModel(model_name)
        response = await genai_model.generate_content_async(
            all_prompt,
            stream=True
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text

    def process_text_sync(self, text: str, prompt: str, model: Optional[str] = None) -> str:
        all_prompt = f"{prompt}\n\n{text}"
        model_name = model or self.default_model
        logger.info(f"Using model: {model_name} for sync processing")
        logger.info(f"Prompt: {all_prompt}")
        genai_model = genai.GenerativeModel(model_name)
        response = genai_model.generate_content(all_prompt)
        return response.text

class GPTProcessor(LLMProcessor):
    def __init__(self, default_model: str = 'gpt-4'):
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OpenAI API key not found in environment variables")
        self.async_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.sync_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.default_model = default_model

    async def process_text(self, text: str, prompt: str, model: Optional[str] = None) -> AsyncGenerator[str, None]:
        all_prompt = f"{prompt}\n\n{text}"
        model_name = model or self.default_model
        logger.info(f"Using model: {model_name} for processing")
        logger.info(f"Prompt: {all_prompt}")
        response = await self.async_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": all_prompt}
            ],
            stream=True
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def process_text_sync(self, text: str, prompt: str, model: Optional[str] = None) -> str:
        all_prompt = f"{prompt}\n\n{text}"
        model_name = model or self.default_model
        logger.info(f"Using model: {model_name} for sync processing")
        logger.info(f"Prompt: {all_prompt}")
        response = self.sync_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": all_prompt}
            ]
        )
        return response.choices[0].message.content

class DeepSeekProcessor(LLMProcessor):
    def __init__(self, default_model: str = 'deepseek-chat'):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise EnvironmentError("DEEPSEEK_API_KEY is not set in environment variables.")
        self.async_client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
        self.sync_client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
        self.default_model = default_model

    async def process_text(self, text: str, prompt: str, model: Optional[str] = None) -> AsyncGenerator[str, None]:
        all_prompt = f"{prompt}\n\n{text}"
        model_name = model or self.default_model
        logger.info(f"Using DeepSeek model: {model_name} for processing")
        response = await self.async_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": all_prompt}],
            stream=True
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def process_text_sync(self, text: str, prompt: str, model: Optional[str] = None) -> str:
        all_prompt = f"{prompt}\n\n{text}"
        model_name = model or self.default_model
        logger.info(f"Using DeepSeek model: {model_name} for sync processing")
        response = self.sync_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": all_prompt}]
        )
        return response.choices[0].message.content

def get_llm_processor(model_name: str) -> LLMProcessor:
    """
    Factory function to get the appropriate LLM processor based on the model name.

    Args:
        model_name (str): The name of the model (e.g., 'gpt-4o', 'gemini-1.5-pro', 'deepseek-chat').

    Returns:
        LLMProcessor: An instance of the corresponding LLM processor.
    
    Raises:
        ValueError: If the model type is unsupported.
    """
    model_name_lower = model_name.lower()
    if model_name_lower.startswith(('gpt-', 'o1-')):
        # Note: 'o1-mini' is a specific model, but we can treat it as part of GPT family for now.
        return GPTProcessor(default_model=model_name)
    elif model_name_lower.startswith('gemini'):
        return GeminiProcessor(default_model=model_name)
    elif model_name_lower.startswith('deepseek'):
        return DeepSeekProcessor(default_model=model_name)
    else:
        # Default to GPT if no specific provider is identified, for backward compatibility.
        logger.warning(f"Unsupported or unrecognized model type: '{model_name}'. Defaulting to GPTProcessor.")
        return GPTProcessor(default_model=model_name)
