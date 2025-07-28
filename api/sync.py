from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from core.app import AnkiVectorApp
from database.manager import DatabaseManager
from models.database import AnkiCard, LearningContent
from models.schemas import BatchSyncLearningContentRequest, SyncCardRequest, SyncLearningContentRequest
from services.card_service import CardService
from services.export_service import ExportService
from database.manager import DatabaseManager

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

db_manager = DatabaseManager()

anki_vector_instance = AnkiVectorApp(db_manager)

router = APIRouter()

@router.post("/sync/set-skip-tag")
async def set_skip_tag(learning_content_id: int, skip_tag: str = "sync::skip") -> Dict[str, Any]:
    """Set skip tag on a card"""
    try:
        with db_manager.get_session() as session:
            existing_card = session.query(AnkiCard).filter_by(
                learning_content_id=learning_content_id
            ).first()
            
            if not existing_card:
                raise HTTPException(status_code=404, detail=f"No AnkiCard found for learning_content_id {learning_content_id}")
            
            # Add skip tag to existing tags
            current_tags = existing_card.tags or []
            if skip_tag not in current_tags:
                current_tags.append(skip_tag)
                existing_card.tags = current_tags
                session.commit()
                
                return {
                    "message": f"Added skip tag '{skip_tag}' to card",
                    "learning_content_id": learning_content_id,
                    "anki_card_id": existing_card.id,
                    "updated_tags": existing_card.tags
                }
            else:
                return {
                    "message": f"Skip tag '{skip_tag}' already exists on card",
                    "learning_content_id": learning_content_id,
                    "anki_card_id": existing_card.id,
                    "current_tags": existing_card.tags
                }
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting skip tag: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync/remove-skip-tag")
async def remove_skip_tag(learning_content_id: int, skip_tag: str = "sync::skip") -> Dict[str, Any]:
    """Remove skip tag from a card"""
    try:
        with db_manager.get_session() as session:
            existing_card = session.query(AnkiCard).filter_by(
                learning_content_id=learning_content_id
            ).first()
            
            if not existing_card:
                raise HTTPException(status_code=404, detail=f"No AnkiCard found for learning_content_id {learning_content_id}")
            
            # Remove skip tag from existing tags
            current_tags = existing_card.tags or []
            if skip_tag in current_tags:
                current_tags.remove(skip_tag)
                existing_card.tags = current_tags
                session.commit()
                
                return {
                    "message": f"Removed skip tag '{skip_tag}' from card",
                    "learning_content_id": learning_content_id,
                    "anki_card_id": existing_card.id,
                    "updated_tags": existing_card.tags
                }
            else:
                return {
                    "message": f"Skip tag '{skip_tag}' not found on card",
                    "learning_content_id": learning_content_id,
                    "anki_card_id": existing_card.id,
                    "current_tags": existing_card.tags
                }
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing skip tag: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sync/analyze-status")
async def analyze_sync_status() -> Dict[str, Any]:
    """Analyze sync status of all learning content"""
    try:
        card_service = CardService(db_manager)
        
        with db_manager.get_session() as session:
            # Get all learning content with their sync status
            learning_contents = session.query(LearningContent).all()
            anki_cards = session.query(AnkiCard).filter(AnkiCard.learning_content_id.isnot(None)).all()
            
            # Create mapping
            card_map = {card.learning_content_id: card for card in anki_cards}
            
            sync_analysis = {
                "synced": [],
                "needs_update": [],
                "not_synced": [],
                "skipped": [],
                "sync_failed": []
            }
            
            for content in learning_contents:
                card = card_map.get(content.id)
                
                if not card:
                    sync_analysis["not_synced"].append({
                        "learning_content_id": content.id,
                        "content_type": content.content_type,
                        "language": content.language
                    })
                elif card_service._should_skip_sync(card):
                    sync_analysis["skipped"].append({
                        "learning_content_id": content.id,
                        "anki_card_id": card.id,
                        "tags": card.tags,
                        "reason": "skip_tag"
                    })
                elif not card.anki_note_id or "sync::fail" in (card.tags or []):
                    sync_analysis["sync_failed"].append({
                        "learning_content_id": content.id,
                        "anki_card_id": card.id,
                        "tags": card.tags,
                        "export_hash": card.export_hash
                    })
                elif card.export_hash:
                    # Would need to check current export hash vs stored - simplified for this analysis
                    sync_analysis["synced"].append({
                        "learning_content_id": content.id,
                        "anki_card_id": card.id,
                        "anki_note_id": card.anki_note_id,
                        "export_hash": card.export_hash[:8] + "..." if card.export_hash else None
                    })
                else:
                    sync_analysis["needs_update"].append({
                        "learning_content_id": content.id,
                        "anki_card_id": card.id,
                        "reason": "no_export_hash"
                    })
            
            return {
                "total_learning_content": len(learning_contents),
                "total_anki_cards": len(anki_cards),
                "analysis": sync_analysis,
                "summary": {
                    "synced_count": len(sync_analysis["synced"]),
                    "needs_update_count": len(sync_analysis["needs_update"]),
                    "not_synced_count": len(sync_analysis["not_synced"]),
                    "skipped_count": len(sync_analysis["skipped"]),
                    "failed_count": len(sync_analysis["sync_failed"])
                }
            }
    except Exception as e:
        logger.error(f"Error analyzing sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync/batch-hash-check")
async def batch_hash_check(learning_content_ids: List[int]) -> Dict[str, Any]:
    """Check multiple learning content items for hash changes"""
    try:
        export_service = ExportService()
        results = {
            "up_to_date": [],
            "needs_update": [],
            "no_card": [],
            "skipped": [],
            "errors": []
        }
        
        card_service = CardService(db_manager)
        
        for content_id in learning_content_ids:
            try:
                # Check existing card first
                with db_manager.get_session() as session:
                    existing_card = session.query(AnkiCard).filter_by(
                        learning_content_id=content_id
                    ).first()
                
                if not existing_card:
                    results["no_card"].append({
                        "learning_content_id": content_id
                    })
                    continue
                
                # Check skip tags first
                if card_service._should_skip_sync(existing_card):
                    results["skipped"].append({
                        "learning_content_id": content_id,
                        "anki_card_id": existing_card.id,
                        "tags": existing_card.tags
                    })
                    continue
                
                # Get current export hash
                export_result = export_service.get_anki_content(content_id)
                if 'error' in export_result:
                    results["errors"].append({
                        "learning_content_id": content_id,
                        "error": export_result['error']
                    })
                    continue
                
                current_hash = export_result['export_hash']
                
                if existing_card.export_hash != current_hash:
                    results["needs_update"].append({
                        "learning_content_id": content_id,
                        "anki_card_id": existing_card.id,
                        "current_hash": current_hash,
                        "stored_hash": existing_card.export_hash
                    })
                else:
                    results["up_to_date"].append({
                        "learning_content_id": content_id,
                        "anki_card_id": existing_card.id,
                        "hash": current_hash
                    })
                    
            except Exception as e:
                results["errors"].append({
                    "learning_content_id": content_id,
                    "error": str(e)
                })
        
        return {
            "total_checked": len(learning_content_ids),
            "summary": {
                "up_to_date": len(results["up_to_date"]),
                "needs_update": len(results["needs_update"]),
                "skipped": len(results["skipped"]),
                "no_card": len(results["no_card"]),
                "errors": len(results["errors"])
            },
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error in batch hash check: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Sync endpoints
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
        card_service = CardService(db_manager)
        result = await card_service.sync_learning_content_to_anki(
            request.learning_content_id,
            request.deck_name
        )
        return result
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
