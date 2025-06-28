"""
Basic tests to verify the Anki Vector application setup
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
import tempfile
import os

from main import AnkiConnectClient, DatabaseManager, AnkiVectorApp, AnkiCard
from config import settings

@pytest.mark.asyncio
async def test_anki_connect_client():
    """Test AnkiConnect client initialization"""
    async with AnkiConnectClient() as client:
        assert client.url == settings.anki_connect_url
        assert client.timeout == settings.anki_connect_timeout

@pytest.mark.asyncio
async def test_database_manager():
    """Test database manager with temporary database"""
    # Create temporary database
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()
    
    try:
        db_url = f"sqlite:///{temp_file.name}"
        db_manager = DatabaseManager(db_url)
        
        # Test that tables are created
        with db_manager.get_session() as session:
            # Try to query the table (should not raise error)
            count = session.query(AnkiCard).count()
            assert count == 0
        
    finally:
        os.unlink(temp_file.name)

@pytest.mark.asyncio
async def test_anki_vector_app_initialization():
    """Test AnkiVectorApp initialization"""
    app = AnkiVectorApp()
    assert app.db_manager is not None

@pytest.mark.asyncio
async def test_mock_embedding_generation():
    """Test mock embedding generation"""
    app = AnkiVectorApp()
    
    # Create a mock card
    class MockCard:
        def __init__(self):
            self.front_text = "Hello"
            self.back_text = "World"
    
    mock_card = MockCard()
    embeddings = app._generate_mock_embeddings(mock_card)
    
    assert "front" in embeddings
    assert "back" in embeddings
    assert "combined" in embeddings
    assert len(embeddings["front"]) == settings.embedding_dimension

def test_settings_loading():
    """Test that settings load correctly"""
    assert settings.database_url is not None
    assert settings.anki_connect_url is not None
    assert settings.embedding_dimension > 0

if __name__ == "__main__":
    # Run tests
    asyncio.run(test_anki_connect_client())
    asyncio.run(test_database_manager())
    asyncio.run(test_anki_vector_app_initialization())
    asyncio.run(test_mock_embedding_generation())
    test_settings_loading()
    print("All basic tests passed!") 
