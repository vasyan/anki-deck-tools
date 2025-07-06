"""
Service for managing Anki card operations
"""
import logging
from typing import Dict, Any, List

from anki.client import AnkiConnectClient
from database.manager import DatabaseManager

logger = logging.getLogger(__name__)

class CardService:
    """Service for Anki card operations"""
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.db_manager = db_manager or DatabaseManager()
    
    async def sync_deck(self, deck_name: str) -> Dict[str, Any]:
        """Sync a specific deck from Anki"""
        print(f"calling sync_deck: {deck_name}")
        try:
            async with AnkiConnectClient() as anki_client:
                # Find all notes in the deck
                query = f'deck:"{deck_name}"'
                note_ids = await anki_client.find_notes(query)
                
                if not note_ids:
                    return {"message": f"No notes found in deck: {deck_name}", "synced": 0}
                
                # Get detailed note information
                notes_info = await anki_client.notes_info(note_ids)

                # Store cards in database
                stored_ids = await self.db_manager.store_anki_cards(notes_info, deck_name)
                
                return {
                    "message": f"Successfully synced deck: {deck_name}",
                    "synced": len(stored_ids),
                    "card_ids": stored_ids
                }
        
        except Exception as e:
            logger.error(f"Error syncing deck {deck_name}: {e}")
            raise
    
    async def sync_all_decks(self) -> Dict[str, Any]:
        """Sync all decks from Anki"""
        try:
            async with AnkiConnectClient() as anki_client:
                deck_names = await anki_client.get_deck_names()
                
                total_synced = 0
                results = {}
                
                for deck_name in deck_names:
                    try:
                        result = await self.sync_deck(deck_name)
                        results[deck_name] = result
                        total_synced += result["synced"]
                    except Exception as e:
                        logger.error(f"Failed to sync deck {deck_name}: {e}")
                        results[deck_name] = {"error": str(e)}
                
                return {
                    "message": f"Synced {total_synced} cards from {len(deck_names)} decks",
                    "total_synced": total_synced,
                    "deck_results": results
                }
        
        except Exception as e:
            logger.error(f"Error syncing all decks: {e}")
            raise 
