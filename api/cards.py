from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from fastapi.params import Form
from database.manager import DatabaseManager
from models.database import AnkiCard, LearningContent
from models.schemas import SyncCardRequest
from services.card_service import CardService
from services.content_renderer import ContentRenderer
from services.export_service import ExportService
from database.manager import DatabaseManager
from models.schemas import AnkiCardResponse, VectorSearchRequest, SyncCardRequest, SyncLearningContentRequest, BatchSyncLearningContentRequest
from fastapi.responses import Response, HTMLResponse
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
        cards = await db_manager.get_cards_by_deck(deck_name)
        return [
            AnkiCardResponse(
                id=card.id,
                anki_note_id=card.anki_note_id,
                deck_name=card.deck_name,
                model_name=card.model_name,
                front_text=card.front_text,
                back_text=card.back_text,
                tags=card.tags if card.tags else [],
                created_at=card.created_at,
                updated_at=card.updated_at,
                is_draft=getattr(card, 'is_draft', 1),
                example=getattr(card, 'example', None)
            )
            for card in cards
        ]
    except Exception as e:
        logger.error(f"Error getting cards for deck {deck_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cards", response_model=List[AnkiCardResponse])
async def get_all_cards(limit: int = 100, offset: int = 0) -> List[AnkiCardResponse]:
    """Get all cards with pagination"""
    try:
        with db_manager.get_session() as session:
            cards = session.query(AnkiCard).offset(offset).limit(limit).all()
            return [
                AnkiCardResponse(
                    id=card.id,
                    anki_note_id=card.anki_note_id,
                    deck_name=card.deck_name,
                    model_name=card.model_name,
                    front_text=card.front_text,
                    back_text=card.back_text,
                    tags=card.tags if card.tags else [],
                    created_at=card.created_at,
                    updated_at=card.updated_at,
                    is_draft=getattr(card, 'is_draft', 1),
                    example=getattr(card, 'example', None)
                )
                for card in cards
            ]
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

@router.get("/cards/{card_id}/render")
async def render_card_content(card_id: int, output_format: str = "html"):
    """Render all content for a card"""
    try:
        renderer = ContentRenderer()
        rendered = renderer.render_card_content(card_id, output_format)
        
        return rendered
    except Exception as e:
        logger.error(f"Error rendering card content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cards/{card_id}/fragments")
async def get_card_fragments(card_id: int):
    """Get fragments used by a card"""
    try:
        renderer = ContentRenderer()
        summary = renderer.get_card_fragments_summary(card_id)
        
        return summary
    except Exception as e:
        logger.error(f"Error getting card fragments: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cards/{card_id}/convert")
async def convert_legacy_card(card_id: int, auto_generate_audio: bool = Form(False)):
    """Convert legacy card content to fragment system"""
    try:
        renderer = ContentRenderer()
        
        # Get TTS service if needed
        tts_service = None
        if auto_generate_audio:
            from services.text_to_voice import TextToSpeechService
            tts_service = TextToSpeechService()
        
        result = renderer.convert_legacy_examples(card_id, auto_generate_audio, tts_service)
        
        return result
    except Exception as e:
        logger.error(f"Error converting card: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cards/{card_id}/preview")
async def preview_card_rendering(card_id: int):
    """Preview how a card would render in different formats"""
    try:
        renderer = ContentRenderer()
        preview = renderer.preview_card_rendering(card_id)
        
        return preview
    except Exception as e:
        logger.error(f"Error previewing card: {e}")
        raise HTTPException(status_code=500, detail=str(e))
