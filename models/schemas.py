"""
Pydantic schemas for API requests and responses
"""
from datetime import datetime
from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field, computed_field
from pydantic import ConfigDict
import base64


# Define reusable type alias for optional metadata dictionaries
Metadata = Optional[Dict[str, Any]]
Tags = Optional[List[str]]
# Define type alias for allowed fragment types
FragmentType = Literal["basic_meaning", "pronunciation_and_tone", "real_life_example", "usage_tip", "target_learning_item"]

class FragmentAssetRowSchema(BaseModel):
    """Schema representing an asset (audio/image/video) attached to a content fragment."""
    id: int
    fragment_id: int
    asset_type: Literal['audio', 'image', 'video']
    asset_data: bytes
    asset_metadata: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(
        json_encoders={bytes: lambda v: base64.b64encode(v).decode()},
        from_attributes=True,
    )


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
    force_update: bool = False

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

class ContentFragmentRowSchema(BaseModel):
    id: int
    native_text: str
    body_text: str
    ipa: Optional[str] = None
    extra: Optional[str] = None
    fragment_type: FragmentType
    assets: Optional[List[FragmentAssetRowSchema]] = None

class ContentFragmentUpdate(BaseModel):
    native_text: Optional[str] = None
    body_text: Optional[str] = None
    ipa: Optional[str] = None
    extra: Optional[str] = None
    fragment_type: Optional[FragmentType] = None
    fragment_metadata: Optional[Metadata] = None

class ContentFragmentCreate(BaseModel):
    native_text: str
    body_text: str
    ipa: Optional[str] = None
    extra: Optional[str] = None
    fragment_type: FragmentType
    fragment_metadata: Optional[Metadata] = None


class ContentFragmentSearchRow(BaseModel):
    learning_content_id: Optional[int] = None
    text_search: Optional[str] = None
    fragment_type: Optional[FragmentType] = None
    has_assets: Optional[bool] = Field(default=None)
    limit: int = 50
    offset: int = 0
    min_rating: Optional[float] = None
    max_rating: Optional[float] = None

class FragmentRankingInput(BaseModel):
    rank_score: float
    assessment_notes: Optional[str] = None
    assessed_by: str = "admin"

class LearningContentFilter(BaseModel):
    """Filter parameters for learning content search"""
    content_type: Optional[str] = None
    language: Optional[str] = None
    difficulty_level: Optional[int] = None
    tags: Optional[List[str]] = None
    text_search: Optional[str] = None
    has_fragments: Optional[bool] = None
    min_fragments_count: Optional[int] = None
    max_fragments_count: Optional[int] = None
    cursor: Optional[int] = None
    model_config = ConfigDict(extra='ignore')

class LearningContentRowSchema(BaseModel):
    id: int
    title: str
    content_type: str
    language: str
    native_text: Optional[str] = None
    translation: Optional[str] = None
    ipa: Optional[str] = None
    difficulty_level: Optional[int] = None
    tags: Tags = None
    content_metadata: Metadata = None
    created_at: datetime
    updated_at: datetime
    last_review_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# class ContentFragmentWithAssetsRowSchema(ContentFragmentRowSchema):
#     audio_asset: Optional[FragmentAssetRowSchema] = None

class LearningContentUpdate(BaseModel):
    # every updatable column is optional
    title: str | None = None
    content_type: str | None = None
    language: str | None = None
    native_text: str | None = None
    difficulty_level: int | None = None
    tags: Tags | None = None
    content_metadata: Metadata | None = None

    model_config = ConfigDict(extra='forbid')  # reject unknown keys

# New schema for create operations (title and content_type required)
class LearningContentCreate(BaseModel):
    title: str
    content_type: str
    language: str = "thai"
    native_text: str | None = None
    difficulty_level: int | None = None
    tags: Tags | None = None
    content_metadata: Metadata | None = None

    model_config = ConfigDict(extra='forbid')

# Schema for list/search results with computed helper flags
class LearningContentSearchRow(LearningContentRowSchema):
    @computed_field(return_type=int)
    def linked_anki_cards_count(self) -> int:  # type: ignore[override]
        return len(getattr(self, "anki_cards", []))

    model_config = ConfigDict(from_attributes=True, extra='allow')

class LearningContentWebExportDTO(BaseModel):
    front: str
    back: str
    examples: Optional[List[ContentFragmentRowSchema]] = None

class AssetRankingInput(BaseModel):
    """Request model for ranking assets"""
    rank_score: float
    assessment_notes: Optional[str] = None
    assessed_by: str = "admin"

class RenderCardInputSchema(BaseModel):
    """Input schema for rendering cards"""
    native_text: str
    translation: str
    ipa: str
    fragments: List[ContentFragmentRowSchema]

class RenderCardOutputSchema(BaseModel):
    """Output schema for rendered cards"""
    front: str
    back: str
    examples: List[ContentFragmentRowSchema]

class SyncLearningContentToAnkiInputSchema(BaseModel):
    """Input schema for syncing learning content to Anki"""
    learning_content_id: int
    front: str
    back: str
    content_hash: str
    assets_to_sync: List[FragmentAssetRowSchema]
    force_update: bool = False

class SyncLearningContentToAnkiOutputSchema(BaseModel):
    """Output schema for Anki sync results"""
    anki_card_id: Optional[int]
    anki_note_id: Optional[int]
    status: Literal["created", "updated", "skipped", "failed"]

class SynthesizeOutput(BaseModel):
    """Output schema for text-to-speech synthesis"""
    audio: bytes
    tts_model: str
