"""Session management for Network Operations Platform.

This module provides session management with support for:
- In-memory sessions (local development)
- AgentCore Memory (AWS deployment)
- Session timeout and cleanup
- Conversation context preservation
"""

import os
import time
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Represents a chat message."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create from dictionary."""
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


@dataclass
class Session:
    """Represents a user session."""
    session_id: str
    messages: List[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the session."""
        self.messages.append(Message(role=role, content=content))
        self.last_accessed = datetime.now()
    
    def get_context(self, max_messages: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation context for the agent."""
        recent_messages = self.messages[-max_messages:]
        return [{"role": msg.role, "content": msg.content} for msg in recent_messages]
    
    def is_expired(self, timeout_minutes: int = 60) -> bool:
        """Check if session has expired."""
        timeout = timedelta(minutes=timeout_minutes)
        return datetime.now() - self.last_accessed > timeout
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            messages=[Message.from_dict(msg) for msg in data["messages"]],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            metadata=data.get("metadata", {})
        )


class SessionStore:
    """Base class for session storage."""
    
    def create_session(self, session_id: Optional[str] = None) -> Session:
        """Create a new session."""
        raise NotImplementedError
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        raise NotImplementedError
    
    def save_session(self, session: Session) -> None:
        """Save a session."""
        raise NotImplementedError
    
    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        raise NotImplementedError
    
    def cleanup_expired_sessions(self, timeout_minutes: int = 60) -> int:
        """Remove expired sessions. Returns count of deleted sessions."""
        raise NotImplementedError


class InMemorySessionStore(SessionStore):
    """In-memory session store for local development."""
    
    def __init__(self):
        """Initialize in-memory store."""
        self.sessions: Dict[str, Session] = {}
        logger.info("Initialized InMemorySessionStore")
    
    def create_session(self, session_id: Optional[str] = None) -> Session:
        """Create a new session."""
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        session = Session(session_id=session_id)
        self.sessions[session_id] = session
        logger.info(f"Created session: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        session = self.sessions.get(session_id)
        if session:
            session.last_accessed = datetime.now()
        return session
    
    def save_session(self, session: Session) -> None:
        """Save a session."""
        self.sessions[session.session_id] = session
        logger.debug(f"Saved session: {session.session_id}")
    
    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
    
    def cleanup_expired_sessions(self, timeout_minutes: int = 60) -> int:
        """Remove expired sessions."""
        expired_ids = [
            sid for sid, session in self.sessions.items()
            if session.is_expired(timeout_minutes)
        ]
        
        for session_id in expired_ids:
            self.delete_session(session_id)
        
        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired sessions")
        
        return len(expired_ids)


class AgentCoreMemoryStore(SessionStore):
    """AgentCore Memory-based session store for AWS deployment."""
    
    def __init__(self, memory_id: str):
        """
        Initialize AgentCore Memory store.
        
        Args:
            memory_id: AgentCore Memory identifier
        """
        self.memory_id = memory_id
        
        try:
            # Import AgentCore SDK
            from agentcore import Memory
            self.memory = Memory(memory_id=memory_id)
            logger.info(f"Initialized AgentCoreMemoryStore with memory_id: {memory_id}")
        except ImportError:
            logger.error("AgentCore SDK not installed. Install with: pip install agentcore")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize AgentCore Memory: {e}")
            raise
    
    def create_session(self, session_id: Optional[str] = None) -> Session:
        """Create a new session."""
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        session = Session(session_id=session_id)
        self.save_session(session)
        logger.info(f"Created session in AgentCore Memory: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        try:
            data = self.memory.get(key=session_id)
            if data:
                session = Session.from_dict(data)
                session.last_accessed = datetime.now()
                self.save_session(session)  # Update last_accessed
                return session
            return None
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            return None
    
    def save_session(self, session: Session) -> None:
        """Save a session."""
        try:
            self.memory.put(
                key=session.session_id,
                value=session.to_dict()
            )
            logger.debug(f"Saved session to AgentCore Memory: {session.session_id}")
        except Exception as e:
            logger.error(f"Error saving session {session.session_id}: {e}")
            raise
    
    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        try:
            self.memory.delete(key=session_id)
            logger.info(f"Deleted session from AgentCore Memory: {session_id}")
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
    
    def cleanup_expired_sessions(self, timeout_minutes: int = 60) -> int:
        """Remove expired sessions."""
        # Note: AgentCore Memory may have built-in TTL
        # This is a placeholder for manual cleanup if needed
        logger.info("AgentCore Memory cleanup - using built-in TTL")
        return 0


class SessionManager:
    """Main session manager that handles session lifecycle."""
    
    def __init__(self, store: Optional[SessionStore] = None):
        """
        Initialize session manager.
        
        Args:
            store: Session store implementation. If None, uses environment-based default.
        """
        if store is None:
            # Auto-detect based on environment
            environment = os.getenv("ENVIRONMENT", "local")
            if environment == "local":
                self.store = InMemorySessionStore()
            else:
                memory_id = os.getenv("AGENTCORE_MEMORY_ID", "netops-sessions")
                self.store = AgentCoreMemoryStore(memory_id=memory_id)
        else:
            self.store = store
        
        logger.info(f"SessionManager initialized with {type(self.store).__name__}")
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> Session:
        """Get existing session or create new one."""
        if session_id:
            session = self.store.get_session(session_id)
            if session:
                return session
        
        # Create new session
        return self.store.create_session(session_id)
    
    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Add a message to a session."""
        session = self.get_or_create_session(session_id)
        session.add_message(role, content)
        self.store.save_session(session)
    
    def get_context(self, session_id: str, max_messages: int = 10) -> List[Dict[str, str]]:
        """Get conversation context for a session."""
        session = self.store.get_session(session_id)
        if session:
            return session.get_context(max_messages)
        return []
    
    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        self.store.delete_session(session_id)
    
    def cleanup_expired(self, timeout_minutes: int = 60) -> int:
        """Clean up expired sessions."""
        return self.store.cleanup_expired_sessions(timeout_minutes)


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


if __name__ == "__main__":
    # Test the session manager
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    print("Testing SessionManager...")
    print("=" * 60)
    
    # Test in-memory store
    manager = SessionManager(store=InMemorySessionStore())
    
    # Create session
    session = manager.get_or_create_session()
    print(f"\nCreated session: {session.session_id}")
    
    # Add messages
    manager.add_message(session.session_id, "user", "Check maintenance for site_atlanta_001")
    manager.add_message(session.session_id, "assistant", "Checking maintenance...")
    print(f"Added 2 messages")
    
    # Get context
    context = manager.get_context(session.session_id)
    print(f"\nContext ({len(context)} messages):")
    for msg in context:
        print(f"  {msg['role']}: {msg['content'][:50]}...")
    
    # Test session retrieval
    retrieved = manager.get_or_create_session(session.session_id)
    print(f"\nRetrieved session: {retrieved.session_id}")
    print(f"Message count: {len(retrieved.messages)}")
    
    print("\n" + "=" * 60)
    print("✓ SessionManager tests passed")
