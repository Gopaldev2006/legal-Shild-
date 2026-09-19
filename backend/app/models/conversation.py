"""
Conversation and ChatMessage models for persistent AI chat.

Relationship hierarchy:
  User
    └── Conversation
          ├── ChatMessage (many)
          └── Document (optional, one)

Security:
  - Every conversation belongs to exactly one user (owner_id)
  - Messages belong to conversations (conversation_id)
  - Authorization: current_user.id == conversation.user_id
"""

import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Enum as SQLEnum, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class ConversationMode(str, enum.Enum):
    """Mode of conversation determines AI behavior and data access"""
    GENERAL = "general"      # General legal Q&A, no document access
    DOCUMENT = "document"    # Chat about a specific uploaded document
    RAG = "rag"             # Retrieval-augmented generation with vector search


class MessageRole(str, enum.Enum):
    """Role of message sender"""
    USER = "user"           # User's question/input
    ASSISTANT = "assistant"  # AI's response
    SYSTEM = "system"       # System messages (e.g., context, instructions)


class Conversation(Base):
    """
    Persistent conversation thread between user and AI assistant.
    
    A conversation may be:
    - General: Legal Q&A without document context
    - Document-specific: Tied to a single uploaded document
    - RAG: Using vector retrieval across user's document corpus
    
    Security:
    - owner_id enforces user isolation
    - document_id (if present) must also belong to owner_id
    """
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Owner relationship (required)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Optional document association (for document-specific chats)
    document_id = Column(
        Integer, 
        ForeignKey("legal_documents.id"), 
        nullable=True, 
        index=True
    )
    
    # Conversation metadata
    title = Column(String(500), nullable=False, default="New Conversation")
    mode = Column(
        SQLEnum(ConversationMode), 
        default=ConversationMode.GENERAL, 
        nullable=False,
        index=True
    )
    
    # Timestamps
    created_at = Column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False,
        index=True
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    document = relationship("LegalDocument", foreign_keys=[document_id])
    messages = relationship(
        "ChatMessage", 
        back_populates="conversation",
        cascade="all, delete-orphan",  # Delete messages when conversation deleted
        order_by="ChatMessage.created_at"
    )
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_conversation_owner_created',   'owner_id', 'created_at'),
        Index('idx_conversation_owner_mode',      'owner_id', 'mode'),
        Index('idx_conversation_owner_updated',   'owner_id', 'updated_at'),  # recency sort
    )


class ChatMessage(Base):
    """
    Individual message within a conversation.
    
    Fields:
    - role: user | assistant | system
    - content: Message text
    - model_used: AI model that generated response (for assistant messages)
    - sources_json: JSON array of source documents/chunks (for RAG responses)
    
    Security:
    - Access controlled via conversation.owner_id
    - Sources must belong to conversation owner
    """
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Conversation relationship (required)
    conversation_id = Column(
        Integer, 
        ForeignKey("conversations.id"), 
        nullable=False, 
        index=True
    )
    
    # Message metadata
    role = Column(SQLEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    
    # AI model tracking (for assistant messages)
    model_used = Column(String(100), nullable=True)  # e.g., "gemini-1.5-flash", "free-engine"
    
    # Source tracking (JSON array for RAG responses)
    # Format: [{"document_id": 4, "document_name": "contract.pdf", "page_number": 7, 
    #          "chunk_id": "chunk_021", "similarity": 0.87}]
    sources_json = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False,
        index=True
    )
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_message_conversation_created', 'conversation_id', 'created_at'),
        Index('idx_message_conversation_role', 'conversation_id', 'role'),
    )
