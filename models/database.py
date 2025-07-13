"""
SQLAlchemy database models for Anki Vector application
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class AnkiCard(Base):
    """SQLAlchemy model for Anki cards"""
    __tablename__ = "anki_cards"
    
    id = Column(Integer, primary_key=True)
    anki_note_id = Column(Integer, unique=True, nullable=True)
    deck_name = Column(String(255), nullable=False)
    model_name = Column(String(255), nullable=True)
    front_text = Column(Text)
    back_text = Column(Text)
    tags = Column(JSON)  # Store as JSON array
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    transcription = Column(Text)
    audio = Column(LargeBinary)  # If you want to use BLOB, use LargeBinary
    example = Column(Text)
    is_draft = Column(Integer, default=1, nullable=False)
    tts_model = Column(Text, nullable=True)  # Store the TTS model used for audio
    
    # Relationship to embeddings
    embeddings = relationship("VectorEmbedding", back_populates="card")

class VectorEmbedding(Base):
    """SQLAlchemy model for vector embeddings"""
    __tablename__ = "vector_embeddings"
    
    id = Column(Integer, primary_key=True)
    card_id = Column(Integer, ForeignKey("anki_cards.id"), nullable=False)
    embedding_type = Column(String(50), nullable=False)  # e.g., 'front', 'back', 'combined'
    vector_data = Column(Text)  # Store as JSON for now, will be BLOB for sqlite-vec
    vector_dimension = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to card
    card = relationship("AnkiCard", back_populates="embeddings") 
