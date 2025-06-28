"""
Configuration management for the Anki Vector application
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    database_url: str = Field(default="sqlite:///anki_vector_db.db", env="DATABASE_URL")
    
    # AnkiConnect
    anki_connect_url: str = Field(default="http://localhost:8765", env="ANKI_CONNECT_URL")
    anki_connect_timeout: int = Field(default=30, env="ANKI_CONNECT_TIMEOUT")
    
    # API
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Embedding Configuration - aligned with embedding processor
    embedding_model: str = Field(default="all-MiniLM-L6-v2", env="EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=384, env="EMBEDDING_DIMENSION")
    embedding_batch_size: int = Field(default=32, env="EMBEDDING_BATCH_SIZE")
    embedding_max_seq_length: int = Field(default=256, env="EMBEDDING_MAX_SEQ_LENGTH")
    embedding_device: str = Field(default="auto", env="EMBEDDING_DEVICE")
    embedding_cache_dir: str = Field(default="./models", env="EMBEDDING_CACHE_DIR")
    
    # External APIs (optional)
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    huggingface_api_key: Optional[str] = Field(default=None, env="HUGGINGFACE_API_KEY")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Global settings instance
settings = Settings() 
