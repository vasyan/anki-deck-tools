"""
Pydantic schemas for API requests and responses
"""
from datetime import datetime
from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field, computed_field
from pydantic import ConfigDict

# Define reusable type alias for optional metadata dictionaries
Metadata = Optional[Dict[str, Any]]
Tags = Optional[List[str]]
# Define type alias for allowed fragment types
FragmentType = Literal["basic_meaning", "pronunciation_and_tone", "real_life_example", "usage_tip"]

class AnkiCardResponse(BaseModel):
    """Response model for Anki cards"""
    id: int
    anki_note_id: Optional[int] = None
    deck_name: str
    model_name: Optional[str] = None
    front_text: Optional[str] = None
    back_text: Optional[str] = None
    tags: Tags = []
    created_at: datetime
    updated_at: datetime
    example: Optional[str] = None

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

class SyncLearningContentRequest(BaseModel):
    """Request model for syncing learning content to Anki"""
    learning_content_id: int
    deck_name: str = "top-thai-2000"

class BatchSyncLearningContentRequest(BaseModel):
    """Request model for batch syncing learning content to Anki"""
    learning_content_ids: List[int]
    deck_name: str = "top-thai-2000"

class ContentFragmentInput(BaseModel):
    learning_content_id: int
    native_text: str
    fragment_type: FragmentType = Field(alias="type")
    body_text: str
    ipa: Optional[str] = None
    extra: Optional[str] = None
    fragment_metadata: Metadata = None

    # Allow population by either alias ('type') or actual field name ('fragment_type')
    model_config = ConfigDict(populate_by_name=True)

class LearningContentRowSchema(BaseModel):
    id: int
    title: str
    content_type: str
    language: str
    front_template: Optional[str] = None
    back_template: Optional[str] = None
    example_template: Optional[str] = None
    difficulty_level: Optional[int] = None
    tags: Tags = None
    content_metadata: Metadata = None

    model_config = ConfigDict(from_attributes=True)

class LearningContentUpdate(BaseModel):
    # every updatable column is optional
    title: str | None = None
    content_type: str | None = None
    language: str | None = None
    front_template: str | None = None
    back_template: str | None = None
    example_template: str | None = None
    difficulty_level: int | None = None
    tags: Tags | None = None
    content_metadata: Metadata | None = None

    model_config = ConfigDict(extra='forbid')  # reject unknown keys

# New schema for create operations (title and content_type required)
class LearningContentCreate(BaseModel):
    title: str
    content_type: str
    language: str = "thai"
    front_template: str | None = None
    back_template: str | None = None
    example_template: str | None = None
    difficulty_level: int | None = None
    tags: Tags | None = None
    content_metadata: Metadata | None = None

    model_config = ConfigDict(extra='forbid')

# Schema for list/search results with computed helper flags
class LearningContentSearchRow(LearningContentRowSchema):
    @computed_field(return_type=bool)
    def has_front_template(self) -> bool:  # type: ignore[override]
        return bool(self.front_template)

    @computed_field(return_type=bool)
    def has_back_template(self) -> bool:  # type: ignore[override]
        return bool(self.back_template)

    @computed_field(return_type=bool)
    def has_example_template(self) -> bool:  # type: ignore[override]
        return bool(self.example_template)

    @computed_field(return_type=int)
    def linked_anki_cards_count(self) -> int:  # type: ignore[override]
        return len(getattr(self, "anki_cards", []))

    model_config = ConfigDict(from_attributes=True, extra='allow')
