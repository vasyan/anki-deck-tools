from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from core.app import AnkiVectorApp
from database.manager import DatabaseManager
from models.schemas import BatchSyncLearningContentRequest, SyncCardRequest, SyncLearningContentRequest, SyncLearningContentToAnkiInputSchema
from services.card_service import CardService
from workflows.anki_builder import AnkiBuilder

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

db_manager = DatabaseManager()

anki_vector_instance = AnkiVectorApp(db_manager)

router = APIRouter()

@router.post("/sync/deck")
async def sync_deck(request: SyncCardRequest) -> Dict[str, Any]:
    """Sync specific deck from Anki"""
    if not request.deck_names or len(request.deck_names) != 1:
        raise HTTPException(status_code=400, detail="Must provide exactly one deck name")

    deck_name = request.deck_names[0]
    try:
        result = await anki_vector_instance.sync_deck(deck_name)
        return result
    except Exception as e:
        logger.error(f"Error syncing deck {deck_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync/all")
async def sync_all_decks() -> Dict[str, Any]:
    """Sync all decks from Anki"""
    try:
        result = await anki_vector_instance.sync_all_decks()
        return result
    except Exception as e:
        logger.error(f"Error syncing all decks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync/learning-content")
async def sync_learning_content_to_anki(request: SyncLearningContentRequest) -> Dict[str, Any]:
    """Sync learning content to Anki via AnkiConnect"""
    try:
        anki_builder = AnkiBuilder()
        rendered_content = await anki_builder.get_rendered_content(request.learning_content_id)
        if not rendered_content:
            logger.error(f"Failed to get rendered content for learning_content_id: {request.learning_content_id}")
            return {}

        content_hash = anki_builder.calculate_content_hash(rendered_content.model_dump())
        assets_to_sync = [fragment.assets[0] for fragment in rendered_content.examples if fragment.assets] if rendered_content.examples else []

        card_service = CardService(db_manager)
        result = await card_service.sync_learning_content_to_anki(
            input=SyncLearningContentToAnkiInputSchema(
                learning_content_id=request.learning_content_id,
                front=rendered_content.front,
                back=rendered_content.back,
                content_hash=content_hash,
                assets_to_sync=assets_to_sync,
                force_update=request.force_update
            ),
        )
        return result.model_dump()
    except Exception as e:
        logger.error(f"Error syncing learning content {request.learning_content_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync/learning-content/batch")
async def batch_sync_learning_content_to_anki(request: BatchSyncLearningContentRequest) -> Dict[str, Any]:
    """Batch sync multiple learning content items to Anki via AnkiConnect"""
    try:
        card_service = CardService(db_manager)
        result = await card_service.batch_sync_learning_content_to_anki(
            request.learning_content_ids,
            request.deck_name
        )
        return result
    except Exception as e:
        logger.error(f"Error in batch sync learning content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync/learning-content/all")
async def sync_all_learning_content_to_anki() -> Dict[str, Any]:
    """Sync all learning content to Anki via AnkiConnect"""
    try:
        card_service = CardService(db_manager)
        result = await card_service.sync_all_learning_content_to_anki()
        return result
    except Exception as e:
        logger.error(f"Error syncing all learning content: {e}")
        raise HTTPException(status_code=500, detail=str(e))
