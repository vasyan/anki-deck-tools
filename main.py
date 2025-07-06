"""
CLI entry point for Anki Vector data management
"""
import asyncio
import logging

from core.app import AnkiVectorApp
from anki.client import AnkiConnectClient
from config import settings

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

async def main():
    """Main function for basic testing"""
    app = AnkiVectorApp()
    
    try:
        # Test AnkiConnect connection
        async with AnkiConnectClient() as client:
            version = await client.get_version()
            print(f"AnkiConnect version: {version}")
            
            decks = await client.get_deck_names()
            print(f"Available decks: {decks}")
        
        print("AnkiVectorApp initialized successfully!")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 
