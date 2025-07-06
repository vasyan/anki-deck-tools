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
