import logging
import time
from abc import ABC, abstractmethod

from openai import OpenAI

from config import config

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all research agents.

    Provides common OpenAI client, retry logic, and structured logging.
    All concrete agents must implement the `run` method.
    """

    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.OPENAI_MODEL
        logger.info(f"Initialised {self.name} with model={self.model}")

    def _call_llm(self, user_message: str, tools: list | None = None) -> str:
        """Call GPT-4o with retry logic and optional tool definitions.

        Args:
            user_message: The prompt to send as the user turn.
            tools: Optional list of OpenAI function/tool definitions.

        Returns:
            The model's text response, or empty string on total failure.

        Raises:
            Exception: Re-raises the last exception after MAX_RETRIES exhausted.
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]

        for attempt in range(config.MAX_RETRIES):
            try:
                kwargs: dict = dict(
                    model=self.model,
                    messages=messages,
                    temperature=0.3,
                    timeout=config.TIMEOUT,
                )
                if tools:
                    kwargs["tools"] = tools

                response = self.client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""

            except Exception as exc:
                logger.warning(
                    f"{self.name} LLM call attempt {attempt + 1}/{config.MAX_RETRIES} failed: {exc}"
                )
                if attempt < config.MAX_RETRIES - 1:
                    sleep_seconds = 2**attempt  # exponential back-off: 1s, 2s, 4s
                    logger.info(f"Retrying in {sleep_seconds}s …")
                    time.sleep(sleep_seconds)
                else:
                    logger.error(f"{self.name} all retry attempts exhausted.")
                    raise

        return ""

    @abstractmethod
    def run(self, state: dict) -> dict:
        """Execute agent logic; receive and return the shared state dict.

        Args:
            state: The shared ResearchState dictionary.

        Returns:
            Updated state dictionary with this agent's outputs populated.
        """
        ...
