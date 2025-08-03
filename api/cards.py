from fastapi import APIRouter, HTTPException
from typing import List

from database.manager import DatabaseManager
from models.database import AnkiCard
from database.manager import DatabaseManager
from models.schemas import AnkiCardResponse
from fastapi.responses import Response
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

db_manager = DatabaseManager()

router = APIRouter()

# Card endpoints
@router.get("/cards/deck", response_model=List[AnkiCardResponse])
async def get_cards_by_deck(deck_name: str) -> List[AnkiCardResponse]:
    """Get all cards for a specific deck"""
    try:
        # TODO: implement
        return []

    except Exception as e:
        logger.error(f"Error getting cards for deck {deck_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cards", response_model=List[AnkiCardResponse])
async def get_all_cards(limit: int = 100, offset: int = 0) -> List[AnkiCardResponse]:
    """Get all cards with pagination"""
    try:
        with db_manager.get_session() as session:
            # TODO: implement
            return []
    except Exception as e:
        logger.error(f"Error getting all cards: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cards/{card_id}/audio")
async def get_card_audio(card_id: int):
	"""Return the audio for a card as an audio file (e.g., mp3)"""
	with db_manager.get_session() as session:
		card = session.get(AnkiCard, card_id)
		if not card or not card.audio:
			raise HTTPException(status_code=404, detail="Card or audio not found")
		# Default to mp3, could be made dynamic if needed
		return Response(card.audio, media_type="audio/mpeg")

# @router.get("/cards/{card_id}/render")
# async def render_card_content(card_id: int, output_format: str = "html"):
#     """Deprecated card rendering endpoint"""
#     raise HTTPException(status_code=501, detail="Card rendering endpoint deprecated")

# @router.get("/cards/{card_id}/fragments")
# async def get_card_fragments(card_id: int):
#     """Deprecated fragments endpoint"""
#     raise HTTPException(status_code=501, detail="Fragment summary endpoint deprecated")

# @router.post("/cards/{card_id}/convert")
# async def convert_legacy_card(card_id: int, auto_generate_audio: bool = Form(False)):
#     """Deprecated conversion endpoint"""
#     raise HTTPException(status_code=501, detail="Convert legacy card endpoint deprecated")

# @router.get("/cards/{card_id}/preview")
# async def preview_card_rendering(card_id: int):
#     """Deprecated preview endpoint"""
#     raise HTTPException(status_code=501, detail="Card preview endpoint deprecated")
