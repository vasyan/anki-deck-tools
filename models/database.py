from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, LargeBinary, Index, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class AnkiCard(Base):
    __tablename__ = "anki_cards"

    id = Column(Integer, primary_key=True)
    anki_note_id = Column(Integer, unique=True, nullable=True)
    deck_name = Column(String(255), nullable=False)
    tags = Column(JSON)  # Store as JSON array
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    learning_content_id = Column(Integer, ForeignKey("learning_content.id"), nullable=True)
    export_hash = Column(Text, nullable=True)  # Track when re-export needed

    embeddings = relationship("VectorEmbedding", back_populates="card")

    learning_content = relationship("LearningContent", back_populates="anki_cards")

class LearningContent(Base):
    __tablename__ = "learning_content"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)              # "กิน (to eat)"
    content_type = Column(String(50), nullable=False)        # 'vocabulary', 'grammar', 'phrase'
    language = Column(String(10), nullable=False)            # 'thai', 'english', etc.

    native_text = Column(Text)
    back_template = Column(Text)

    # Metadata and classification
    difficulty_level = Column(Integer)        # 1-5 scale
    tags = Column(JSON, nullable=True)                       # ['beginner', 'pronouns', etc.]
    content_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    anki_cards = relationship("AnkiCard", back_populates="learning_content")
    fragments = relationship("ContentFragment", back_populates="learning_content")

    __table_args__ = (
        Index('idx_learning_content_type', 'content_type'),
        Index('idx_learning_content_language', 'language'),
        Index('idx_learning_content_title', 'title'),
    )

class ContentFragment(Base):
    __tablename__ = "content_fragments"

    id = Column(Integer, primary_key=True)
    native_text = Column(Text, nullable=False)
    body_text = Column(Text, nullable=False)
    ipa = Column(Text)
    extra = Column(Text)
    fragment_type = Column(String(50), nullable=False)  # `basic_meaning` | `pronunciation_and_tone` | `usage_example` | `usage_tip`
    fragment_metadata = Column(JSON)  # Extensible metadata (difficulty, frequency, etc.)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    learning_content_id = Column(Integer, ForeignKey("learning_content.id"), nullable=False)

    assets = relationship("FragmentAsset", back_populates="fragment", cascade="all, delete-orphan")
    learning_content = relationship("LearningContent", back_populates="fragments")

    __table_args__ = (
        Index('idx_fragment_type', 'fragment_type'),
        Index('idx_fragment_text', 'native_text'),
    )

class FragmentAsset(Base):
    __tablename__ = "fragment_assets"

    id = Column(Integer, primary_key=True)
    fragment_id = Column(Integer, ForeignKey("content_fragments.id"), nullable=False)
    asset_type = Column(String(20), nullable=False)  # 'audio', 'image', 'video'
    asset_data = Column(LargeBinary)  # Store the actual asset data
    asset_metadata = Column(JSON)  # TTS model, voice, quality, speaker info, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100))  # Who created this asset (system, operator, speaker)

    fragment = relationship("ContentFragment", back_populates="assets")
    rankings = relationship("FragmentAssetRanking", back_populates="asset", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_fragment_asset_type', 'fragment_id', 'asset_type'),
    )

class VectorEmbedding(Base):
    __tablename__ = "vector_embeddings"

    id = Column(Integer, primary_key=True)
    card_id = Column(Integer, ForeignKey("anki_cards.id"), nullable=False)
    embedding_type = Column(String(50), nullable=False)  # e.g., 'front', 'back', 'combined'
    vector_data = Column(Text)  # Store as JSON for now, will be BLOB for sqlite-vec
    vector_dimension = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    card = relationship("AnkiCard", back_populates="embeddings")

# TODO: figure out how it should be used
class FragmentAssetRanking(Base):
    __tablename__ = "fragment_asset_rankings"

    id = Column(Integer, primary_key=True)
    fragment_id = Column(Integer, ForeignKey("content_fragments.id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("fragment_assets.id"), nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)  # Currently selected/active asset
    rank_score = Column(Float, default=0.0)  # Quality ranking by operators
    assessed_by = Column(String(100))  # Who assessed this asset
    assessment_notes = Column(Text)  # Notes about the assessment
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    fragment = relationship("ContentFragment")
    asset = relationship("FragmentAsset", back_populates="rankings")

    __table_args__ = (
        Index('idx_fragment_active', 'fragment_id', 'is_active'),
        Index('idx_asset_ranking', 'asset_id', 'rank_score'),
    )
