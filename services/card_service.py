"""
Service for managing Anki card operations
"""
from datetime import UTC
import datetime
import logging
from typing import Dict, Any, List, Optional, cast

from anki.client import AnkiConnectClient
from models.database import AnkiCard
from models.schemas import (
    FragmentAssetRowSchema,
    SyncLearningContentToAnkiInputSchema,
    SyncLearningContentToAnkiOutputSchema
)
from database.manager import DatabaseManager
import base64
import asyncio
from utils.tag_manager import TagManager
from utils.content_hash import NoteChangeDetector, ContentHasher
from config import settings

# Default deck name used across the service
DEFAULT_DECK = "top-thai-2000"

logger = logging.getLogger(__name__)


class CardService:
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self.tag_manager = TagManager(settings.sync_tag_prefix)
        self.change_detector = NoteChangeDetector()
        self.content_hasher = ContentHasher()

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

    async def get_note_changes(
        self,
        anki_note_id: int,
        expected_fields: Dict[str, str],
        expected_anki_user_tags: List[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze what changes would be made to an Anki note

        This compares expected content (from database) with actual content (in Anki)
        to detect modifications made by the Anki user (learner).

        Returns:
            Dictionary with change analysis and recommendations
        """
        async with AnkiConnectClient() as anki_client:
            notes_info = await anki_client.notes_info([anki_note_id])

            if not notes_info:
                return {"error": f"Note {anki_note_id} not found"}

            note_info = notes_info[0]
            expected_anki_user_tags = expected_anki_user_tags or []

            # Detect modifications made by Anki user (learner)
            changes = self.change_detector.detect_anki_user_modifications(
                expected_fields,
                expected_anki_user_tags,
                note_info
            )

            return {
                "note_id": anki_note_id,
                "changes": changes,
                "current_fields": note_info.get("fields", {}),
                "current_tags": note_info.get("tags", []),
                "recommendation": "skip" if changes.anki_user_modified_fields and settings.preserve_user_modifications else "proceed"
            }

    async def smart_update_note(
        self,
        anki_note_id: int,
        new_fields: Dict[str, str],
        sync_status: str = "success",
        force_update: bool = False
    ) -> Dict[str, Any]:
        """
        Smart update of Anki note that preserves Anki user (learner) modifications

        This method respects customizations made by the Anki user while applying
        content updates from the database.

        Args:
            anki_note_id: Anki note ID to update
            new_fields: New field values from database content
            sync_status: Sync status tag to add
            force_update: Whether to force update despite anki user modifications

        Returns:
            Update result with details about what was changed
        """
        async with AnkiConnectClient() as anki_client:
            # Get current note state
            notes_info = await anki_client.notes_info([anki_note_id])

            if not notes_info:
                return {"success": False, "error": f"Note {anki_note_id} not found"}

            current_note = notes_info[0]
            current_fields = current_note.get("fields", {})
            current_tags = current_note.get("tags", [])

            # Detect what would change - check for Anki user modifications
            changes = self.change_detector.detect_anki_user_modifications(
                new_fields,
                [],  # We don't expect specific anki user tags
                current_note
            )

            # print(f"changes: {changes}")

            # Decide whether to proceed - check if we should preserve Anki user modifications
            should_skip = self.change_detector.should_skip_update(
                changes,
                force_update,
                settings.preserve_user_modifications  # Setting controls preserving Anki user changes
            )

            print(f"should_skip: {should_skip}")

            if should_skip:
                logger.info(f"Skipping update of note {anki_note_id} due to Anki user modifications")
                # Still update tags to reflect skip status
                new_tags = self.tag_manager.merge_tags(current_tags, "skipped")
                await anki_client.update_note(anki_note_id, tags=new_tags)

                return {
                    "success": True,
                    "action": "skipped",
                    "reason": "anki_user_modifications_detected",
                    "anki_user_modified_fields": changes.anki_user_modified_fields,
                    "tags_updated": new_tags
                }

            # Proceed with smart update
            fields_to_update = {}

            if settings.merge_strategy == "conservative" and not force_update:
                # Only update fields that weren't modified by Anki user (learner)
                for field_name, new_value in new_fields.items():
                    if field_name not in changes.anki_user_modified_fields:
                        fields_to_update[field_name] = new_value
            else:  # aggressive
                # Update all fields, potentially overwriting Anki user changes
                fields_to_update = new_fields.copy()

            # Smart tag merge
            new_tags = self.tag_manager.merge_tags(current_tags, sync_status)

            # Perform the update
            await anki_client.update_note(
                anki_note_id,
                fields=fields_to_update,
                tags=new_tags
            )

            logger.info(f"Smart updated note {anki_note_id}: fields={list(fields_to_update.keys())}, tags={new_tags}")

            return {
                "success": True,
                "action": "updated",
                "fields_updated": list(fields_to_update.keys()),
                "fields_skipped": [f for f in new_fields.keys() if f not in fields_to_update],
                "tags_updated": new_tags,
                "anki_user_modifications_preserved": len(changes.anki_user_modified_fields) > 0
            }

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
        ) -> SyncLearningContentToAnkiOutputSchema:
        try:
            with self.db_manager.get_session() as session:
                existing_card = session.query(AnkiCard).filter_by(
                    learning_content_id=input.learning_content_id
                ).first()
                if existing_card:
                    if cast(str, existing_card.export_hash) == input.content_hash and not input.force_update:
                        # Content unchanged, just update sync tag
                        new_tags = self.tag_manager.merge_tags(
                            getattr(existing_card, "tags", []) or [],
                            "skipped"
                        )
                        setattr(existing_card, "tags", new_tags)
                        setattr(existing_card, "updated_at", datetime.datetime.now(UTC))
                        session.commit()

                        return SyncLearningContentToAnkiOutputSchema(
                            anki_card_id=cast(int, existing_card.id),
                            anki_note_id=cast(int, existing_card.anki_note_id),
                            status="skipped",
                        )
                    else:
                        # Content changed, perform smart update
                        async with AnkiConnectClient() as anki_client:
                            await self._upload_audio_assets_with_replace(anki_client, input.assets_to_sync)

                        # Use smart update system
                        update_result = await self.smart_update_note(
                            cast(int, existing_card.anki_note_id),
                            {
                                "Front": input.front,
                                "Back": input.back,
                            },
                            sync_status="success",
                            force_update=input.force_update
                        )

                        # print(f"update_result: {update_result}")

                        if not update_result["success"]:
                            logger.error(f"Smart update failed for note {existing_card.anki_note_id}: {update_result}")
                            return SyncLearningContentToAnkiOutputSchema(
                                anki_card_id=cast(int, existing_card.id),
                                anki_note_id=cast(int, existing_card.anki_note_id),
                                status="failed",
                            )

                        # Update database record
                        setattr(existing_card, "export_hash", input.content_hash)
                        setattr(existing_card, "tags", update_result["tags_updated"])
                        setattr(existing_card, "updated_at", datetime.datetime.now(UTC))
                        session.commit()

                        # Determine status based on what actually happened
                        if update_result["action"] == "skipped":
                            status = "skipped"
                        elif update_result.get("anki_user_modifications_preserved", False):
                            status = "updated"  # partial update preserving anki user changes
                        else:
                            status = "updated"

                        return SyncLearningContentToAnkiOutputSchema(
                            anki_card_id=cast(int, existing_card.id),
                            anki_note_id=cast(int, existing_card.anki_note_id),
                            status=status,
                        )
                # create new card
                else:
                    logger.info(f"Creating new card for learning content {input.learning_content_id}")

                    async with AnkiConnectClient() as anki_client:
                        await self._upload_audio_assets_with_replace(anki_client, input.assets_to_sync)

                        # Create new tags using tag manager
                        new_tags = self.tag_manager.create_sync_tags(["success", "new"])

                        note_id = await anki_client.add_note(  # type: ignore[reportUnknownMemberType]
                            note={
                                "deckName": DEFAULT_DECK,
                                "fields": {
                                    "Front": input.front,
                                    "Back": input.back,
                                },
                                "modelName": "Basic",
                                "tags": new_tags,
                            }
                        )
                    logger.info(f"New card created with note_id: {note_id}")
                    new_card = AnkiCard(
                        learning_content_id=input.learning_content_id,
                        export_hash=input.content_hash,
                        deck_name=DEFAULT_DECK,
                        tags=new_tags,
                        anki_note_id=note_id,
                    )
                    session.add(new_card)
                    session.commit()

                    return SyncLearningContentToAnkiOutputSchema(
                        anki_card_id=cast(int, new_card.id),
                        anki_note_id=cast(int, new_card.anki_note_id),
                        status="created",
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
