"""AgentCore Memory integration via Strands Hooks.

Provides short-term memory (conversation history within a session) and
long-term memory (extracted preferences/facts across sessions) using
Amazon Bedrock AgentCore Memory.

Local development: Falls back to in-memory storage when MEMORY_ID is not set.
Production: Uses AgentCore Memory when MEMORY_ID env var is configured.
"""

import os
import sys
import logging
import traceback
from typing import Optional

from strands.hooks import (
    AgentInitializedEvent,
    HookProvider,
    HookRegistry,
    MessageAddedEvent,
)

# Use a dedicated logger with explicit DEBUG level so we see everything
logger = logging.getLogger("memory_hook")
logger.setLevel(logging.DEBUG)
# Ensure output goes to stdout (AgentCore captures stdout)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setLevel(logging.DEBUG)
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    logger.addHandler(_handler)

MEMORY_ID = os.getenv("MEMORY_ID", "")
MEMORY_REGION = os.getenv("AWS_REGION", "us-east-1")

logger.info(f"[MEMORY_HOOK MODULE] Loading. MEMORY_ID={MEMORY_ID!r}, "
            f"REGION={MEMORY_REGION}")

# Auto-discover memory ID from agentcore config if not set via env var
if not MEMORY_ID:
    try:
        import yaml
        config_paths = [
            os.path.join(os.path.dirname(__file__), ".bedrock_agentcore.yaml"),
            os.path.join(
                os.path.dirname(__file__), "..", ".bedrock_agentcore.yaml"
            ),
        ]
        for path in config_paths:
            if os.path.isfile(path):
                with open(path) as f:
                    cfg = yaml.safe_load(f)
                for agent_cfg in (cfg.get("agents") or {}).values():
                    mem = agent_cfg.get("memory", {})
                    if mem.get("memory_id"):
                        MEMORY_ID = mem["memory_id"]
                        logger.info(
                            f"[MEMORY_HOOK] Auto-discovered MEMORY_ID "
                            f"from config: {MEMORY_ID}"
                        )
                        break
                if MEMORY_ID:
                    break
    except Exception as e:
        logger.debug(f"[MEMORY_HOOK] Could not auto-discover memory ID: {e}")


class AgentCoreMemoryHook(HookProvider):
    """Strands hook that persists conversations to AgentCore Memory.

    On agent init: loads the last K conversation turns into context.
    On message added: saves the message to AgentCore Memory (STM + LTM).
    """

    def __init__(
        self,
        memory_id: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self.memory_id = memory_id or MEMORY_ID
        self.region = region or MEMORY_REGION
        self._client = None
        self._session_mgr = None

        logger.info(
            f"[MEMORY_HOOK __init__] memory_id={self.memory_id!r}, "
            f"region={self.region}"
        )

        if not self.memory_id:
            logger.info(
                "[MEMORY_HOOK __init__] MEMORY_ID not set — disabled"
            )
            return

        try:
            from bedrock_agentcore.memory import MemoryClient
            from bedrock_agentcore.memory.session import MemorySessionManager
            self._client = MemoryClient(region_name=self.region)
            self._session_mgr_cls = MemorySessionManager
            logger.info(
                f"[MEMORY_HOOK __init__] ✓ MemoryClient + "
                f"MemorySessionManager imported OK"
            )
        except ImportError as e:
            logger.warning(
                f"[MEMORY_HOOK __init__] bedrock-agentcore not installed: {e}"
            )
        except Exception as e:
            logger.warning(
                f"[MEMORY_HOOK __init__] Failed to init: {e}\n"
                f"{traceback.format_exc()}"
            )

    @property
    def enabled(self) -> bool:
        return bool(self.memory_id and self._client)

    def _get_session(self, agent):
        """Get or create a MemorySessionManager for the agent's session."""
        # Read from custom attributes set by agentcore_app.py
        session_id = getattr(agent, "_netops_session_id", "default")
        actor_id = getattr(agent, "_netops_actor_id", "user")

        logger.info(
            f"[MEMORY_HOOK _get_session] "
            f"actor_id={actor_id!r}, session_id={session_id!r}, "
            f"memory_id={self.memory_id!r}"
        )

        # Also log whether the attributes actually exist on the agent
        has_sid = hasattr(agent, "_netops_session_id")
        has_aid = hasattr(agent, "_netops_actor_id")
        logger.info(
            f"[MEMORY_HOOK _get_session] "
            f"has _netops_session_id={has_sid}, "
            f"has _netops_actor_id={has_aid}"
        )

        from bedrock_agentcore.memory.session import MemorySessionManager
        mgr = MemorySessionManager(
            memory_id=self.memory_id,
            region_name=self.region,
        )
        session = mgr.create_memory_session(
            actor_id=actor_id,
            session_id=session_id,
        )
        logger.info(
            f"[MEMORY_HOOK _get_session] MemorySession created OK "
            f"(actor={actor_id}, session={session_id})"
        )
        return session

    def on_agent_initialized(self, event: AgentInitializedEvent):
        """Load recent conversation history into the agent's context.

        NOTE: This fires once during Agent() construction, BEFORE
        _netops_session_id / _netops_actor_id are set by agentcore_app.py.
        So it will use defaults ("default" / "user") — that's expected.
        """
        logger.info(
            "[MEMORY_HOOK on_agent_initialized] FIRED. "
            f"enabled={self.enabled}"
        )
        if not self.enabled:
            return

        try:
            session = self._get_session(event.agent)
            logger.info(
                "[MEMORY_HOOK on_agent_initialized] "
                "Calling get_last_k_turns(k=5)..."
            )
            turns = session.get_last_k_turns(k=5)
            logger.info(
                f"[MEMORY_HOOK on_agent_initialized] "
                f"Got {len(turns)} turns"
            )

            if turns:
                context_lines = []
                for turn in turns:
                    for msg in turn:
                        role = msg.get("role", "unknown")
                        text = msg.get("content", {}).get("text", "")
                        if text:
                            context_lines.append(f"{role}: {text[:200]}")

                if context_lines:
                    context_str = "\n".join(context_lines)
                    event.agent.system_prompt += (
                        f"\n\n--- Previous conversation context ---\n"
                        f"{context_str}\n"
                        f"--- End of context ---"
                    )
                    logger.info(
                        f"[MEMORY_HOOK on_agent_initialized] "
                        f"Loaded {len(context_lines)} messages into context"
                    )
        except Exception as e:
            logger.warning(
                f"[MEMORY_HOOK on_agent_initialized] FAILED: {e}\n"
                f"{traceback.format_exc()}"
            )

    def on_message_added(self, event: MessageAddedEvent):
        """Save each message to AgentCore Memory."""
        logger.info(
            f"[MEMORY_HOOK on_message_added] FIRED. enabled={self.enabled}"
        )
        if not self.enabled:
            logger.info(
                "[MEMORY_HOOK on_message_added] Skipping — not enabled"
            )
            return

        try:
            from bedrock_agentcore.memory.constants import (
                ConversationalMessage,
                MessageRole,
            )

            msg = event.agent.messages[-1]
            role_str = msg.get("role", "user")
            logger.info(
                f"[MEMORY_HOOK on_message_added] "
                f"Message role={role_str!r}, "
                f"content type={type(msg.get('content', '')).__name__}"
            )

            session = self._get_session(event.agent)

            # Extract text content from the message
            content = msg.get("content", "")
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and "text" in block:
                        text_parts.append(block["text"])
                content = " ".join(text_parts)
            elif isinstance(content, dict):
                content = content.get("text", str(content))

            if not content or not isinstance(content, str):
                logger.info(
                    f"[MEMORY_HOOK on_message_added] "
                    f"Skipping — no text content "
                    f"(content={type(content).__name__}: "
                    f"{str(content)[:100]!r})"
                )
                return

            # Only save user and assistant messages
            if role_str not in ("user", "assistant"):
                logger.info(
                    f"[MEMORY_HOOK on_message_added] "
                    f"Skipping role={role_str!r} (not user/assistant)"
                )
                return

            role = (
                MessageRole.ASSISTANT
                if role_str == "assistant"
                else MessageRole.USER
            )

            truncated = content[:2000]
            logger.info(
                f"[MEMORY_HOOK on_message_added] "
                f"Calling session.add_turns() — "
                f"role={role_str}, content_len={len(truncated)}"
            )
            result = session.add_turns(
                messages=[ConversationalMessage(truncated, role)]
            )
            logger.info(
                f"[MEMORY_HOOK on_message_added] ✅ add_turns SUCCESS. "
                f"Result: {result}"
            )

        except Exception as e:
            logger.warning(
                f"[MEMORY_HOOK on_message_added] FAILED: {e}\n"
                f"{traceback.format_exc()}"
            )

    def register_hooks(self, registry: HookRegistry):
        """Register both hooks with the agent."""
        logger.info("[MEMORY_HOOK register_hooks] Registering callbacks")
        registry.add_callback(
            AgentInitializedEvent, self.on_agent_initialized
        )
        registry.add_callback(MessageAddedEvent, self.on_message_added)
        logger.info(
            "[MEMORY_HOOK register_hooks] ✓ Registered "
            "AgentInitializedEvent + MessageAddedEvent"
        )


def create_memory_hook() -> Optional[AgentCoreMemoryHook]:
    """Create a memory hook if MEMORY_ID is configured.

    Returns None if memory is not configured (local dev without memory).
    """
    logger.info("[MEMORY_HOOK create_memory_hook] Called")
    hook = AgentCoreMemoryHook()
    if hook.enabled:
        logger.info(
            f"[MEMORY_HOOK create_memory_hook] ✓ Hook enabled "
            f"(memory_id={hook.memory_id})"
        )
        return hook
    logger.info("[MEMORY_HOOK create_memory_hook] Hook NOT enabled")
    return None
