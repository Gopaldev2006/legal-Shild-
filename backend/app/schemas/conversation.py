"""
Pydantic schemas for Conversation and ChatMessage API.

Request/Response models for:
- Creating conversations
- Listing conversations
- Retrieving conversation history
- Sending messages
- Deleting conversations
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ============================================================================
# Source Tracking
# ============================================================================

class MessageSourceSchema(BaseModel):
    """Source document/chunk reference for RAG responses"""
    model_config = ConfigDict(from_attributes=True)

    document_id: int
    document_name: str
    page_number: Optional[int] = None
    chunk_id: Optional[str] = None
    similarity: Optional[float] = None
    matter_id: Optional[str] = None
    jurisdiction: Optional[str] = None


# ============================================================================
# ChatMessage Schemas
# ============================================================================

class ChatMessageBase(BaseModel):
    """Base chat message fields"""
    role: str = Field(..., description="Message role: user | assistant | system")
    content: str = Field(..., description="Message content")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = ['user', 'assistant', 'system']
        if v not in allowed:
            raise ValueError(f"Role must be one of: {', '.join(allowed)}")
        return v


class ChatMessageCreate(ChatMessageBase):
    """Request schema for creating a new message"""
    pass


class ChatMessageResponse(ChatMessageBase):
    """Response schema for a chat message"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    model_used: Optional[str] = None
    sources: Optional[List[MessageSourceSchema]] = None
    created_at: datetime


# ============================================================================
# Conversation Schemas
# ============================================================================

class ConversationBase(BaseModel):
    """Base conversation fields"""
    title: str = Field(default="New Conversation", max_length=500)
    mode: str = Field(default="general", description="Conversation mode: general | document | rag")

    @field_validator('mode')
    @classmethod
    def validate_mode(cls, v: str) -> str:
        allowed = ['general', 'document', 'rag']
        if v not in allowed:
            raise ValueError(f"Mode must be one of: {', '.join(allowed)}")
        return v


class ConversationCreate(ConversationBase):
    """Request schema for creating a new conversation"""
    document_id: Optional[int] = Field(
        default=None,
        description="Optional document ID for document-specific chat"
    )


class ConversationUpdate(BaseModel):
    """Request schema for updating a conversation"""
    title: Optional[str] = Field(None, max_length=500)


class ConversationListItem(ConversationBase):
    """Response schema for conversation in list view"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    document_id: Optional[int] = None
    message_count: int = Field(default=0, description="Number of messages in conversation")
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationBase):
    """Response schema for detailed conversation view with messages"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    document_id: Optional[int] = None
    document_filename: Optional[str] = None
    messages: List[ChatMessageResponse] = []
    created_at: datetime
    updated_at: datetime


class ConversationResponse(ConversationBase):
    """Response schema for conversation without messages"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    document_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Message Sending
# ============================================================================

class SendMessageRequest(BaseModel):
    """Request schema for sending a message and getting AI response"""
    message: str = Field(..., min_length=1, max_length=10000, description="User message")
    model_preference: Optional[str] = Field(
        default=None,
        description="Preferred AI model (e.g., 'gemini', 'free')"
    )


class SendMessageResponse(BaseModel):
    """Response schema after sending a message"""
    model_config = ConfigDict(from_attributes=True)

    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    conversation: ConversationResponse


# ============================================================================
# List/Pagination
# ============================================================================

class ConversationListResponse(BaseModel):
    """Response schema for listing conversations"""
    conversations: List[ConversationListItem]
    total: int
    page: int
    page_size: int
    has_more: bool


class ConversationHistoryResponse(BaseModel):
    """Response schema for conversation history with messages"""
    conversation: ConversationDetail
    total_messages: int
