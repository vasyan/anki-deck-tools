"""
Service for managing Anki card operations
"""
import logging
from typing import Dict, Any, List, Optional, Literal, cast

from pydantic import BaseModel

from anki.client import AnkiConnectClient
from models.database import AnkiCard
from models.schemas import LearningContentRowSchema
from database.manager import DatabaseManager
import base64
import asyncio

from services.fragment_asset_manager import FragmentAssetRowSchema

# Default deck name used across the service
DEFAULT_DECK = "top-thai-2000"

logger = logging.getLogger(__name__)

# TODO: extract to separate file to prevent cycle imports
class SyncLearningContentToAnkiInputSchema(BaseModel):
    learning_content_id: int
    front: str
    back: str
    content_hash: str
    assets_to_sync: List[FragmentAssetRowSchema]

class SyncLearningContentToAnkiOutputSchema(BaseModel):
    anki_card_id: Optional[int]
    anki_note_id: Optional[int]
    status: Literal["created", "updated", "skipped", "failed"]

class CardService:
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    async def sync_deck(self, deck_name: str) -> Dict[str, Any]:
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

    def _should_skip_sync(self, anki_card: AnkiCard) -> bool:
        if not getattr(anki_card, "tags", None):
            return False

        skip_patterns = [
            "sync::skip",
            "sync::skip_update",
            "sync::no_update",
            "skip::sync",
            "skip::update"
        ]

        tags = getattr(anki_card, "tags", [])

        for tag in tags:
            if tag in skip_patterns:
                logger.info(f"Skipping sync for card {anki_card.id} due to tag: {tag}")
                return True

        return False

    ## TODO: fix it, can be useful
    async def batch_sync_learning_content_to_anki(self, learning_content_ids: List[int], deck_name: str = DEFAULT_DECK, concurrency: int = 5) -> Dict[str, Any]:
        item_results: List[Dict[str, Any]] = []

        semaphore = asyncio.Semaphore(concurrency)

        async def _process(lc_id: int):
            async with semaphore:
                try:
                    res = await self.sync_learning_content_to_anki(lc_id, deck_name)
                    item_results.append({"learning_content_id": lc_id, **res})
                except Exception as exc:
                    logger.error(f"Error in batch sync for learning_content {lc_id}: {exc}")
                    item_results.append({"learning_content_id": lc_id, "error": str(exc)})

        await asyncio.gather(*[_process(lc_id) for lc_id in learning_content_ids])

        return {
            "total": len(learning_content_ids),
            "results": item_results
        }

    async def sync_learning_content_to_anki(
            self,
            input: SyncLearningContentToAnkiInputSchema,
            force_update: bool = False,
        ) -> SyncLearningContentToAnkiOutputSchema:
        try:
            with self.db_manager.get_session() as session:
                existing_card = session.query(AnkiCard).filter_by(
                    learning_content_id=input.learning_content_id
                ).first()
                if existing_card:
                    if cast(str, existing_card.export_hash) == input.content_hash and not force_update:
                        return SyncLearningContentToAnkiOutputSchema(
                            anki_card_id=cast(int, existing_card.id),
                            anki_note_id=cast(int, existing_card.anki_note_id),
                            status="skipped",
                        )
                    else:
                        setattr(existing_card, "export_hash", input.content_hash)
                        setattr(existing_card, "front_text", input.front)
                        setattr(existing_card, "back_text", input.back)
                        session.commit()

                        async with AnkiConnectClient() as anki_client:
                            await self._upload_audio_assets_with_replace(anki_client, input.assets_to_sync)
                            await anki_client.update_note(  # type: ignore[reportUnknownMemberType]
                                cast(int, existing_card.anki_note_id),
                                fields={
                                    "Front": input.front,
                                    "Back": input.back,
                                },
                                tags=["sync::success"],
                            )

                        return SyncLearningContentToAnkiOutputSchema(
                            anki_card_id=cast(int, existing_card.id),
                            anki_note_id=cast(int, existing_card.anki_note_id),
                            status="updated",
                        )

            # If we reach this point, either no existing card was found or the creation path
            # is not yet implemented. Return a descriptive failure so the caller can handle it.
            return SyncLearningContentToAnkiOutputSchema(
                anki_card_id=None,
                anki_note_id=None,
                status="failed",
            )
        except Exception as e:
            logger.error(f"Error syncing learning content {input.learning_content_id}: {e}")
            return SyncLearningContentToAnkiOutputSchema(
                anki_card_id=None,
                anki_note_id=None,
                status="failed",
            )

    async def _upload_audio_assets_with_replace(self, anki_client: AnkiConnectClient, assets: List[FragmentAssetRowSchema]) -> None:
        for asset in assets:
            existing_files = await anki_client._request("getMediaFilesNames", {"pattern": f"asset_{asset.id}.mp3"}) # type: ignore[reportUnknownMemberType]
            if existing_files:
                await anki_client._request("deleteMediaFile", {"filename": f"asset_{asset.id}.mp3"}) # type: ignore[reportUnknownMemberType]
            await anki_client._request(  # type: ignore[reportUnknownMemberType]
                "storeMediaFile",
                {
                    "filename": f"asset_{asset.id}.mp3",
                    "data": base64.b64encode(asset.asset_data).decode(),
                },
            )
