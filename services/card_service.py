"""
Service for managing Anki card operations
"""
import logging
from typing import Dict, Any, List, Optional, Literal, cast

from openai import BaseModel

from anki.client import AnkiConnectClient
from database.manager import DatabaseManager
from models.database import AnkiCard, LearningContent
from models.schemas import LearningContentRowSchema
from services.export_service import ExportService
import base64
import asyncio

# Default deck name used across the service
DEFAULT_DECK = "top-thai-2000"

logger = logging.getLogger(__name__)

class SyncLearningContentToAnkiInputSchema(BaseModel):
    lc_data: LearningContentRowSchema
    front: str
    back: str
    content_hash: str

class SyncLearningContentToAnkiOutputSchema(BaseModel):
    anki_card_id: Optional[int]
    anki_note_id: Optional[int]
    status: Literal["created", "updated", "skipped", "failed"]

class CardService:
    """Service for Anki card operations"""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self.export_service = ExportService()

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

    # ---------------------------------------------------------------------
    # Helper utilities
    # ---------------------------------------------------------------------

    async def _ensure_deck(self, anki_client, deck_name: str) -> None:
        """Create deck in Anki if it doesn't exist."""
        await anki_client.create_deck(deck_name)

    async def _ensure_model(self, anki_client, model_name: str, field_names: List[str]) -> None:
        """Create a basic model with the supplied fields if missing."""
        existing_models = await anki_client.model_names()
        if model_name not in existing_models:
            card_templates = [{
                "Name": "Card 1",
                "Front": "{{Front}}",
                "Back": "{{Back}}"
            }]
            await anki_client.create_model(model_name, field_names, card_templates)

    def _make_audio_payload(self, card) -> Optional[List[Dict[str, Any]]]:
        """Return AnkiConnect-compatible audio payload if card has audio."""
        if getattr(card, "audio", None):
            return [{
                "data": base64.b64encode(card.audio).decode("utf-8"),
                "filename": f"card_{card.id}.mp3",
                "fields": ["Audio"]
            }]
        return None

    async def sync_learning_content_to_anki(self, learning_content_id: int, deck_name: str = DEFAULT_DECK) -> Dict[str, Any]:
        """
        Sync learning_content to Anki via AnkiConnect.
        Creates anki_card row, renders templates, uploads to Anki, and updates status.

        Args:
            learning_content_id: ID of learning content to sync
            deck_name: Target deck name (default: "top-thai-2000")

        Returns:
            Dictionary with sync result and details
        """
        try:
            # Step 1: Check if learning content exists and get current export hash
            with self.db_manager.get_session() as session:
                learning_content = session.get(LearningContent, learning_content_id)
                if not learning_content:
                    return {"error": f"Learning content {learning_content_id} not found"}

                # Check if anki_card already exists for this learning_content
                existing_card = session.query(AnkiCard).filter_by(
                    learning_content_id=learning_content_id
                ).first()

            # Step 2: Get rendered content and hash (ExportService does NO database writes)
            export_result = self.export_service.get_anki_content(learning_content_id)
            if 'error' in export_result:
                return {"error": f"Failed to get content: {export_result['error']}"}

            rendered_content = export_result['rendered_content']
            current_export_hash = export_result['export_hash']

            # Validate that we have front and back content
            if not rendered_content.get('front') or not rendered_content.get('back'):
                return {"error": "Learning content must have both front_template and back_template"}

            # Step 3: Handle existing card - check skip tags first, then hash comparison
            if existing_card:
                # Check if card is marked to skip sync
                if self._should_skip_sync(existing_card):
                    return {
                        "message": f"AnkiCard for learning_content {learning_content_id} is marked to skip sync",
                        "anki_card_id": existing_card.id,
                        "anki_note_id": existing_card.anki_note_id,
                        "tags": existing_card.tags,
                        "status": "skipped"
                    }

                # Compare export hashes to see if content has changed
                if existing_card.export_hash == current_export_hash:
                    return {
                        "message": f"AnkiCard for learning_content {learning_content_id} is already up to date",
                        "anki_card_id": existing_card.id,
                        "anki_note_id": existing_card.anki_note_id,
                        "status": "up_to_date"
                    }

                # Content has changed - update existing card
                try:
                    return await self._update_existing_anki_card(
                        existing_card, rendered_content, current_export_hash, deck_name, learning_content
                    )
                except Exception as e:
                    logger.error(f"Error updating existing card: {e}")
                    return {"error": f"Failed to update existing card: {str(e)}"}

            # Step 4: Create new anki_card record for new learning content
            with self.db_manager.get_session() as session:
                anki_card = AnkiCard(
                    learning_content_id=learning_content_id,
                    deck_name=deck_name,
                    tags=["sync::in-progress"],
                    export_hash=current_export_hash
                )
                session.add(anki_card)
                session.flush()  # Get the ID
                anki_card_id = anki_card.id
                session.commit()

            # Step 4: Upload to Anki via AnkiConnect
            try:
                async with AnkiConnectClient() as anki_client:
                    # Ensure deck and model exist
                    await self._ensure_deck(anki_client, deck_name)

                    # Prepare note fields
                    note_fields = {
                        "Front": rendered_content['front'],
                        "Back": rendered_content['back']
                    }

                    # Add example if present
                    if rendered_content.get('example'):
                        note_fields["Example"] = rendered_content['example']

                    # Determine model name and ensure it exists
                    field_names = list(note_fields.keys())
                    model_name = f"{deck_name}_Model"

                    await self._ensure_model(anki_client, model_name, field_names)

                    # Create note in Anki
                    note = {
                        "deckName": deck_name,
                        "modelName": model_name,
                        "fields": note_fields,
                        "tags": learning_content.tags or []
                    }

                    anki_note_id = await anki_client.add_note(note)

                    if anki_note_id:
                        # Step 5: Update anki_card with success status
                        with self.db_manager.get_session() as session:
                            anki_card = session.get(AnkiCard, anki_card_id)
                            if anki_card:
                                anki_card.anki_note_id = anki_note_id
                                anki_card.tags = ["sync::success"]
                                anki_card.export_hash = current_export_hash
                                session.commit()

                        return {
                            "message": f"Successfully synced learning_content {learning_content_id} to Anki",
                            "anki_card_id": anki_card_id,
                            "anki_note_id": anki_note_id,
                            "deck_name": deck_name,
                            "status": "success"
                        }
                    else:
                        # Upload failed - update status
                        with self.db_manager.get_session() as session:
                            anki_card = session.get(AnkiCard, anki_card_id)
                            if anki_card:
                                anki_card.tags = ["sync::fail"]
                                session.commit()

                        return {
                            "error": "Failed to create note in Anki (AnkiConnect returned None)",
                            "anki_card_id": anki_card_id,
                            "status": "failed"
                        }

            except Exception as e:
                # Step 6: Update anki_card with failure status
                logger.error(f"Error uploading to Anki: {e}")
                with self.db_manager.get_session() as session:
                    anki_card = session.get(AnkiCard, anki_card_id)
                    if anki_card:
                        anki_card.tags = ["sync::fail"]
                        session.commit()

                return {
                    "error": f"Failed to upload to Anki: {str(e)}",
                    "anki_card_id": anki_card_id,
                    "status": "failed"
                }

        except Exception as e:
            logger.error(f"Error syncing learning content {learning_content_id}: {e}")
            return {"error": f"Sync failed: {str(e)}"}

    def _should_skip_sync(self, anki_card) -> bool:
        if not anki_card.tags:
            return False

        skip_patterns = [
            "sync::skip",
            "sync::skip_update",
            "sync::no_update",
            "skip::sync",
            "skip::update"
        ]

        tags = anki_card.tags if isinstance(anki_card.tags, list) else []

        for tag in tags:
            if tag in skip_patterns:
                logger.info(f"Skipping sync for card {anki_card.id} due to tag: {tag}")
                return True

        return False

    async def _update_existing_anki_card(self, existing_card, rendered_content, current_export_hash, deck_name, learning_content) -> Dict[str, Any]:
        """Helper method to update an existing Anki card when content has changed"""
        try:
            # Update local card status to in-progress
            with self.db_manager.get_session() as session:
                card = session.get(AnkiCard, existing_card.id)
                if card:
                    card.tags = ["sync::in-progress"]
                    session.commit()

            async with AnkiConnectClient() as anki_client:
                # Prepare note fields
                note_fields = {
                    "Front": rendered_content['front'],
                    "Back": rendered_content['back']
                }

                # Add example if present
                if rendered_content.get('example'):
                    note_fields["Example"] = rendered_content['example']

                # Update existing note in Anki
                if existing_card.anki_note_id:
                    await anki_client.update_note(
                        existing_card.anki_note_id,
                        fields=note_fields,
                        tags=learning_content.tags or []
                    )

                    # Update local record with success status
                    with self.db_manager.get_session() as session:
                        card = session.get(AnkiCard, existing_card.id)
                        if card:
                            card.tags = ["sync::success", "sync::updated"]
                            card.export_hash = current_export_hash
                            session.commit()

                    return {
                        "message": f"Successfully updated learning_content {learning_content.id} in Anki",
                        "anki_card_id": existing_card.id,
                        "anki_note_id": existing_card.anki_note_id,
                        "deck_name": deck_name,
                        "status": "updated"
                    }
                else:
                    # Existing card doesn't have anki_note_id - treat as new sync
                    logger.warning(f"Existing card {existing_card.id} has no anki_note_id, creating new note")

                    # Ensure deck exists
                    await self._ensure_deck(anki_client, deck_name)

                    # Determine model name and ensure it exists
                    field_names = list(note_fields.keys())
                    model_name = f"{deck_name}_Model"

                    await self._ensure_model(anki_client, model_name, field_names)

                    # Create note in Anki
                    note = {
                        "deckName": deck_name,
                        "modelName": model_name,
                        "fields": note_fields,
                        "tags": learning_content.tags or []
                    }

                    anki_note_id = await anki_client.add_note(note)

                    if anki_note_id:
                        # Update local record with success status
                        with self.db_manager.get_session() as session:
                            card = session.get(AnkiCard, existing_card.id)
                            if card:
                                card.anki_note_id = anki_note_id
                                card.tags = ["sync::success", "sync::created"]
                                card.export_hash = current_export_hash
                                session.commit()

                        return {
                            "message": f"Successfully created note for learning_content {learning_content.id} in Anki",
                            "anki_card_id": existing_card.id,
                            "anki_note_id": anki_note_id,
                            "deck_name": deck_name,
                            "status": "created"
                        }
                    else:
                        # Update with failure status
                        with self.db_manager.get_session() as session:
                            card = session.get(AnkiCard, existing_card.id)
                            if card:
                                card.tags = ["sync::fail"]
                                session.commit()

                        return {
                            "error": "Failed to create note in Anki (AnkiConnect returned None)",
                            "anki_card_id": existing_card.id,
                            "status": "failed"
                        }

        except Exception as e:
            logger.error(f"Error updating existing Anki card: {e}")
            # Update with failure status
            with self.db_manager.get_session() as session:
                card = session.get(AnkiCard, existing_card.id)
                if card:
                    card.tags = ["sync::fail"]
                    session.commit()

            return {
                "error": f"Failed to update Anki card: {str(e)}",
                "anki_card_id": existing_card.id,
                "status": "failed"
            }

    async def batch_sync_learning_content_to_anki(self, learning_content_ids: List[int], deck_name: str = DEFAULT_DECK, concurrency: int = 5) -> Dict[str, Any]:
        """
        Batch-sync multiple learning_content items to Anki and return a concise per-item outcome list.

        Args:
            learning_content_ids: IDs to sync.
            deck_name: Target deck.

        Returns:
            Dict with total count and per-item results (success or error).
        """
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

    # actually unused now, keep as a reference
    async def publish_draft_cards(self, deck_name: str = DEFAULT_DECK, model_name: str | None = None, limit: int | None = None) -> Dict[str, Any]:
        """
        Publish all draft cards in a deck to Anki, ensuring model consistency and migrating existing notes if needed.
        Args:
            deck_name: The name of the deck to publish to.
            model_name: Optional. If not provided, a new model will be created based on all fields in the deck.
            limit: Optional. Max number of draft cards to upload.
        Returns:
            Summary dict with counts and details of successes/failures.
        """
        from models.database import AnkiCard

        # Step 1: Gather all cards in the deck to determine superset of fields
        with self.db_manager.get_session() as session:
            all_cards = session.query(AnkiCard).filter_by(deck_name=deck_name).all()
            draft_cards = [c for c in all_cards if c.is_draft == 1]
            if limit:
                draft_cards = draft_cards[:limit]

        if not draft_cards:
            return {"message": f"No draft cards found in deck: {deck_name}", "published": 0}

        # Determine superset of fields
        field_names = set(["Front", "Back"])  # Always present
        extra_field_map = {
            "audio": "Audio",
            "example": "Example",
            "transcription": "Transcription",
        }
        for card in all_cards:
            for attr, anki_field in extra_field_map.items():
                if getattr(card, attr, None) is not None:
                    field_names.add(anki_field)
        field_names = list(field_names)

        # Step 2: Ensure model exists in Anki
        async with AnkiConnectClient() as anki_client:
            # Always ensure the deck exists before proceeding
            await self._ensure_deck(anki_client, deck_name)
            model_to_use = model_name
            if not model_to_use:
                # Generate a model name based on deck and fields
                model_to_use = f"{deck_name}_CustomModel_{'_'.join(field_names)}"
            # Ensure model exists with required fields
            await self._ensure_model(anki_client, model_to_use, field_names)

            # Step 3: Migrate existing notes in deck to new model if needed
            # Find all notes in Anki for this deck
            note_ids = await anki_client.find_notes(f'deck:"{deck_name}"')
            if note_ids:
                notes_info = await anki_client.notes_info(note_ids)
                for note in notes_info:
                    if note.get("modelName") != model_to_use:
                        # Build new fields dict: copy existing, set new fields to empty
                        new_fields = {f: note["fields"].get(f, {"value": ""})["value"] if f in note["fields"] else "" for f in field_names}
                        await anki_client.update_note_model(note["noteId"], model_to_use, new_fields, note.get("tags", []))

            # Step 4: Upload draft cards
            results: List[Dict[str, Any]] = []
            for card in draft_cards:
                note_fields = {
                    "Front": card.front_text or "",
                    "Back": card.back_text or "",
                    "Example": getattr(card, "example", "") or "",
                    "Transcription": getattr(card, "transcription", "") or "",
                }
                # Audio handling via helper
                audio_payload = self._make_audio_payload(card)
                # Remove fields not in model
                note_fields = {k: v for k, v in note_fields.items() if k in field_names}
                note = {
                    "deckName": deck_name,
                    "modelName": model_to_use,
                    "fields": note_fields,
                    "tags": card.tags or [],
                }
                if audio_payload:
                    note["audio"] = audio_payload
                try:
                    result = await anki_client.add_note(note)
                    if result:
                        self.db_manager.mark_card_synced(card.id, result, model_to_use)
                        results.append({"card_id": card.id, "note_id": result, "status": "success"})
                    else:
                        self.db_manager.add_tag_to_card(card.id, "sync::failed")
                        results.append({"card_id": card.id, "status": "failed", "error": "AnkiConnect returned None"})
                except Exception as e:
                    logger.error(f"Failed to upload card {card.id}: {e}")
                    self.db_manager.add_tag_to_card(card.id, "sync::failed")
                    results.append({"card_id": card.id, "status": "failed", "error": str(e)})

        return {
            "total": len(results),
            "deck_name": deck_name,
            "model_name": model_to_use,
            "results": results
        }

    async def sync_learning_content_to_anki(self, input: SyncLearningContentToAnkiInputSchema) -> SyncLearningContentToAnkiOutputSchema:
        """
        Sync learning_content to Anki via AnkiConnect.
        Creates or updates an anki_card row, uploads to Anki, and updates status.
        """
        try:
            with self.db_manager.get_session() as session:
                existing_card = session.query(AnkiCard).filter_by(
                    learning_content_id=input.lc_data.id
                ).first()
                if existing_card:
                    if cast(str, existing_card.export_hash) == input.content_hash:
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
                            await anki_client.update_note(  # type: ignore[reportUnknownMemberType]
                                cast(int, existing_card.anki_note_id),
                                fields={"Front": input.front, "Back": input.back},
                                tags=["sync::success"]
                            )

                        return SyncLearningContentToAnkiOutputSchema(
                            anki_card_id=cast(int, existing_card.id),
                            anki_note_id=cast(int, existing_card.anki_note_id),
                            status="updated",
                        )
        except Exception as e:
            logger.error(f"Error syncing learning content {input.lc_data.id}: {e}")
            return SyncLearningContentToAnkiOutputSchema(
                anki_card_id=None,
                anki_note_id=None,
                status="failed",
            )
