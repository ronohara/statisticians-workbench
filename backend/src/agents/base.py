"""
Agent Framework base classes.
AIAgent — abstract base class for all AI-powered agents.
AgentFactory — registry and factory for agent instantiation.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type

from src.chat.connection import get_connection_details
from src.utils.ai_limits import resolve_ai_limits_for_model
from src.chat.language import language_instruction
from src.chat.providers.base import ProviderFactory
from src.utils.encryption import decrypt_field

logger = logging.getLogger(__name__)


class AIAgent(ABC):
    """
    Abstract base class for all AI-powered agents in the workbench.

    Encapsulates the common lifecycle:
        1. Resolve AI connection details and create a provider
        2. Build a domain-specific system prompt
        3. Call the AI provider
        4. Optionally parse structured output

    Subclasses only need to implement build_system_prompt().
    Connection management, provider creation, error handling, and
    structured output parsing are inherited.
    """

    def __init__(
        self,
        db_pool,
        connection_id: int,
        user_id: str,
        model: Optional[str] = None,
        language: str = "en",
    ):
        """
        Initialize the agent by resolving connection details and creating a provider.

        Args:
            db_pool: PostgreSQL connection pool
            connection_id: The AI connection ID to use
            user_id: The user making the request
            model: Optional model override
            language: Language for error messages and prompts
        """
        self.db_pool = db_pool
        self.connection_id = connection_id
        self.user_id = user_id
        self.model = model
        self.language = language
        self._provider = None
        self._conn_details = None

    async def _resolve_connection(self) -> Dict[str, Any]:
        """Resolve and cache AI connection details."""
        if self._conn_details is None:
            self._conn_details = await get_connection_details(
                self.db_pool, self.connection_id, self.user_id
            )
        return self._conn_details

    async def _get_provider(self):
        """Get or create the AI provider instance."""
        if self._provider is None:
            conn = await self._resolve_connection()
            try:
                api_key = decrypt_field(conn["apiKey"])
            except Exception:
                api_key = conn["apiKey"]

            self._provider = ProviderFactory.create(
                conn["provider"],
                api_key=api_key,
                endpoint=conn.get("endpoint"),
            )
        return self._provider

    @abstractmethod
    async def build_system_prompt(self, **context) -> str:
        """
        Build the system prompt for this agent.

        Each concrete agent implements this with domain-specific instructions.
        Context can include dataset schema, database tables, sample data, etc.

        Returns:
            The system prompt string.
        """
        pass

    async def ask(self, user_message: str, **context) -> str:
        """
        Send a user message to the AI and return the text response.

        Args:
            user_message: The user's question or instruction.
            **context: Passed to build_system_prompt().

        Returns:
            The AI's text response.
        """
        provider = await self._get_provider()
        system_prompt = await self.build_system_prompt(**context)
        system_prompt = language_instruction(self.language) + system_prompt

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        call_kwargs = {"messages": messages}
        if self.model:
            call_kwargs["model"] = self.model

        # The limits in force for this (connection, model) pair — the agent has both.
        async with self.db_pool.acquire() as limits_conn:
            limits = await resolve_ai_limits_for_model(
                limits_conn, self.connection_id, self.model or ""
            )
        call_kwargs["temperature"] = limits.temperature
        call_kwargs["max_tokens"] = limits.max_tokens
        call_kwargs["timeout"] = float(limits.timeout_seconds)

        response = await provider.call(**call_kwargs)
        return response.get("content", "")

    async def ask_structured(
        self, user_message: str, output_schema: Dict[str, Any], **context
    ) -> Dict[str, Any]:
        """
        Ask the AI and parse a structured JSON response.

        Appends JSON output instructions to the system prompt, then attempts
        to parse the response as JSON. Falls back to the raw text if parsing fails.

        Args:
            user_message: The user's question or instruction.
            output_schema: JSON schema or field descriptions to request.
            **context: Passed to build_system_prompt().

        Returns:
            Parsed JSON dict, or {"_raw": "...", "_error": "..."} on failure.
        """
        provider = await self._get_provider()
        system_prompt = await self.build_system_prompt(**context)
        system_prompt = language_instruction(self.language) + system_prompt

        schema_instruction = (
            "\n\nIMPORTANT: Respond ONLY with a valid JSON object matching this schema:\n"
            + json.dumps(output_schema, indent=2)
            + "\nDo not include any text outside the JSON object."
        )

        messages = [
            {"role": "system", "content": system_prompt + schema_instruction},
            {"role": "user", "content": user_message},
        ]

        call_kwargs = {"messages": messages}
        if self.model:
            call_kwargs["model"] = self.model

        # The limits in force for this (connection, model) pair — the agent has both.
        async with self.db_pool.acquire() as limits_conn:
            limits = await resolve_ai_limits_for_model(
                limits_conn, self.connection_id, self.model or ""
            )
        call_kwargs["temperature"] = limits.temperature
        call_kwargs["max_tokens"] = limits.max_tokens
        call_kwargs["timeout"] = float(limits.timeout_seconds)

        response = await provider.call(**call_kwargs)
        content = response.get("content", "")

        try:
            # Handle markdown-wrapped JSON
            text = content.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            return json.loads(text.strip())
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"Failed to parse structured response from agent")
            return {"_raw": content, "_error": "Failed to parse JSON response"}


class AgentFactory:
    """
    Registry and factory for AIAgent subclasses.

    Usage:
        # Register
        AgentFactory.register("dataset_cleaner", DatasetCleanerAgent)

        # Create
        agent = AgentFactory.create("dataset_cleaner", db_pool, connection_id=1, user_id="abc")
    """

    _agents: Dict[str, Type[AIAgent]] = {}

    @classmethod
    def register(cls, name: str, agent_cls: Type[AIAgent]) -> None:
        """Register an agent class under a name."""
        cls._agents[name] = agent_cls

    @classmethod
    def create(cls, name: str, **kwargs) -> AIAgent:
        """
        Create an agent instance by name.

        Args:
            name: The registered agent name.
            **kwargs: Passed to the agent constructor.

        Returns:
            An instance of the requested agent.

        Raises:
            ValueError: If the agent name is not registered.
        """
        agent_cls = cls._agents.get(name)
        if agent_cls is None:
            raise ValueError(
                f"Unknown agent: '{name}'. Available: {list(cls._agents.keys())}"
            )
        return agent_cls(**kwargs)

    @classmethod
    def list_agents(cls) -> List[str]:
        """Return the list of registered agent names."""
        return list(cls._agents.keys())
