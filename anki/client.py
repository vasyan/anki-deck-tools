"""
AnkiConnect client for communicating with Anki application
"""
import logging
from typing import Dict, List, Any

import httpx

from config import settings

logger = logging.getLogger(__name__)

class AnkiConnectClient:
    """Client for communicating with AnkiConnect"""
    
    def __init__(self, url: str = None, timeout: int = None):
        self.url = url or settings.anki_connect_url
        self.timeout = timeout or settings.anki_connect_timeout
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def _request(self, action: str, params: Dict = None) -> Any:
        """Make a request to AnkiConnect"""
        data = {
            "action": action,
            "version": 6,
            "params": params or {}
        }
        
        try:
            response = await self.client.post(self.url, json=data)
            response.raise_for_status()
            
            result = response.json()
            if result.get("error"):
                raise Exception(f"AnkiConnect error: {result['error']}")
            
            return result.get("result")
        except httpx.RequestError as e:
            raise Exception(f"Failed to connect to AnkiConnect: {e}")
    
    async def get_version(self) -> int:
        """Get AnkiConnect version"""
        return await self._request("version")
    
    async def get_deck_names(self) -> List[str]:
        """Get all deck names"""
        return await self._request("deckNames")
    
    async def find_notes(self, query: str) -> List[int]:
        """Find notes by query"""
        return await self._request("findNotes", {"query": query})
    
    async def notes_info(self, note_ids: List[int]) -> List[Dict]:
        """Get detailed info for notes"""
        return await self._request("notesInfo", {"notes": note_ids}) 

    async def create_deck(self, deck_name: str) -> Any:
        """Create a new deck in Anki if it does not exist."""
        return await self._request("createDeck", {"deck": deck_name})

    async def model_names(self) -> List[str]:
        """Get all model (note type) names in Anki."""
        return await self._request("modelNames")

    async def model_field_names(self, model_name: str) -> List[str]:
        """Get all field names for a given model (note type)."""
        return await self._request("modelFieldNames", {"modelName": model_name})

    async def create_model(self, model_name: str, in_order_fields: List[str], card_templates: List[dict], css: str = None, is_cloze: bool = False) -> Any:
        """Create a new model (note type) in Anki."""
        params = {
            "modelName": model_name,
            "inOrderFields": in_order_fields,
            "cardTemplates": card_templates,
            "isCloze": is_cloze
        }
        if css:
            params["css"] = css
        return await self._request("createModel", params)

    async def add_note(self, note: dict) -> Any:
        """Add a single note to Anki."""
        return await self._request("addNote", {"note": note})

    async def add_notes(self, notes: List[dict]) -> Any:
        """Add multiple notes to Anki."""
        return await self._request("addNotes", {"notes": notes})

    async def update_note_model(self, note_id: int, model_name: str, fields: dict, tags: List[str] = None) -> Any:
        """Update a note's model and fields in Anki."""
        params = {
            "note": {
                "id": note_id,
                "modelName": model_name,
                "fields": fields
            }
        }
        if tags is not None:
            params["note"]["tags"] = tags
        return await self._request("updateNoteModel", params)

    async def update_note(self, note_id: int, fields: dict = None, tags: List[str] = None) -> Any:
        """Update a note's fields and/or tags without changing the model."""
        params = {
            "note": {
                "id": note_id
            }
        }
        if fields is not None:
            params["note"]["fields"] = fields
        if tags is not None:
            params["note"]["tags"] = tags
        return await self._request("updateNote", params) 
