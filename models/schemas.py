"""
Pydantic schemas for API requests and responses
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class AnkiCardResponse(BaseModel):
    """Response model for Anki cards"""
    id: int
    anki_note_id: int
    deck_name: str
    model_name: str
    front_text: Optional[str] = None
    back_text: Optional[str] = None
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime

class VectorSearchRequest(BaseModel):
    """Request model for vector search"""
    query_text: str
    query_embedding: Optional[List[float]] = None
    top_k: int = Field(default=10, ge=1, le=100)
    deck_name: Optional[str] = None
    embedding_type: str = Field(default="combined")

class SyncCardRequest(BaseModel):
    """Request model for syncing cards"""
    deck_names: Optional[List[str]] = None
    force_update: bool = False 
