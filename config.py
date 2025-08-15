"""
Configuration management for the Anki Vector application
"""
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
    openai_model: str = Field(default="gpt-3.5-turbo", env="OPENAI_MODEL")
    huggingface_api_key: Optional[str] = Field(default=None, env="HUGGINGFACE_API_KEY")


    # TTS Configuration
    openai_tts_model: str = Field(default="tts-1", env="OPENAI_TTS_MODEL")
    openai_tts_format: str = Field(default="mp3", env="OPENAI_TTS_FORMAT")
    openai_tts_rate_limit: int = Field(default=60, env="OPENAI_TTS_RATE_LIMIT")
    openai_tts_voice: str = Field(default="alloy", env="OPENAI_TTS_VOICE")

    # LLM Studio
    lm_studio_api_base: str = Field(default="http://127.0.0.1:1234/v1", env="LM_STUDIO_API_BASE")

    # Local models
    local_model_thai: str = Field(default="lm_studio/typhoon2.1-gemma3-4b-mlx", env="LOCAL_MODEL_THAI")  # type: ignore
    
    # Smart Anki Update Configuration
    preserve_user_modifications: bool = Field(default=True)
    sync_tag_prefix: str = Field(default="sync::")
    merge_strategy: str = Field(default="conservative")  # conservative or aggressive

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Global settings instance
settings = Settings()
