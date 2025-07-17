"""
Service for managing Anki card operations
"""
import logging
from typing import Dict, Any, List

from anki.client import AnkiConnectClient
from database.manager import DatabaseManager
from models.database import AnkiCard, ExampleAudio
from sqlalchemy import func
import base64

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

    async def publish_draft_cards(self, deck_name: str, model_name: str = None, limit: int = None) -> Dict[str, Any]:
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
        import base64

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
            await anki_client.create_deck(deck_name)
            model_to_use = model_name
            if not model_to_use:
                # Generate a model name based on deck and fields
                model_to_use = f"{deck_name}_CustomModel_{'_'.join(field_names)}"
            existing_models = await anki_client.model_names()
            model_exists = False
            if model_to_use in existing_models:
                model_fields = await anki_client.model_field_names(model_to_use)
                if set(model_fields) == set(field_names):
                    model_exists = True
            if not model_exists:
                # Create model with all fields and a basic card template
                card_templates = [{
                    "Name": "Card 1",
                    "Front": "{{Front}}",
                    "Back": "{{Back}}"
                }]
                await anki_client.create_model(model_to_use, field_names, card_templates)

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
            success, failed = [], []
            for card in draft_cards:
                note_fields = {
                    "Front": card.front_text or "",
                    "Back": card.back_text or "",
                    "Example": getattr(card, "example", "") or "",
                    "Transcription": getattr(card, "transcription", "") or "",
                }
                # Audio handling: attach as base64 if present
                audio_payload = None
                if getattr(card, "audio", None):
                    # AnkiConnect expects audio as a dict with base64 or file path
                    audio_payload = [{
                        "data": base64.b64encode(card.audio).decode("utf-8"),
                        "filename": f"card_{card.id}.mp3",
                        "fields": ["Audio"]
                    }]
                    # Do NOT set note_fields["Audio"] here; AnkiConnect will insert the [sound:...] tag automatically
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
                        success.append(card.id)
                    else:
                        self.db_manager.add_tag_to_card(card.id, "sync::failed")
                        failed.append(card.id)
                except Exception as e:
                    logger.error(f"Failed to upload card {card.id}: {e}")
                    self.db_manager.add_tag_to_card(card.id, "sync::failed")
                    failed.append(card.id)

        return {
            "message": f"Published {len(success)} draft cards to Anki deck '{deck_name}' (model: {model_to_use})",
            "published": len(success),
            "failed": len(failed),
            "success_ids": success,
            "failed_ids": failed
        } 

    async def add_example_audio(self, card_id: int, example_text: str, audio_blob: bytes, tts_model: str = None, order_index: int = None) -> int:
        """Add audio for a specific example"""
        with self.db_manager.get_session() as session:
            # Get current max order_index for this card
            if order_index is None:
                max_order = session.query(func.max(ExampleAudio.order_index))\
                    .filter_by(card_id=card_id).scalar() or -1
                order_index = max_order + 1
            example_audio = ExampleAudio(
                card_id=card_id,
                audio_blob=audio_blob,
                example_text=example_text,
                tts_model=tts_model,
                order_index=order_index
            )
            session.add(example_audio)
            session.commit()
            return example_audio.id

    async def get_example_audios(self, card_id: int) -> list:
        """Get all example audios for a card"""
        with self.db_manager.get_session() as session:
            audios = session.query(ExampleAudio)\
                .filter_by(card_id=card_id)\
                .order_by(ExampleAudio.order_index)\
                .all()
            return [
                {
                    "id": audio.id,
                    "example_text": audio.example_text,
                    "audio_blob": audio.audio_blob,
                    "tts_model": audio.tts_model,
                    "order_index": audio.order_index,
                    "created_at": audio.created_at
                }
                for audio in audios
            ]

    async def generate_example_audios(self, card_id: int, examples: list) -> list:
        """Generate TTS audio for multiple examples and store them"""
        from services.text_to_voice import TextToSpeechService
        tts_service = TextToSpeechService()
        audio_ids = []
        for i, example_text in enumerate(examples):
            try:
                result = tts_service.synthesize(example_text)
                audio_blob = result["audio"]
                tts_model = result["tts_model"]
                audio_id = await self.add_example_audio(
                    card_id=card_id,
                    example_text=example_text,
                    audio_blob=audio_blob,
                    tts_model=tts_model,
                    order_index=i
                )
                audio_ids.append(audio_id)
            except Exception as e:
                logger.error(f"Failed to generate audio for example {i}: {e}")
        return audio_ids

    async def get_card_with_examples(self, card_id: int) -> dict:
        """Get card and all example audios"""
        with self.db_manager.get_session() as session:
            card = session.query(AnkiCard).get(card_id)
            if not card:
                return None
            example_audios = session.query(ExampleAudio)\
                .filter_by(card_id=card_id)\
                .order_by(ExampleAudio.order_index)\
                .all()
            return {
                "id": card.id,
                "front_text": card.front_text,
                "back_text": card.back_text,
                "audio": card.audio,
                "example": card.example,
                "example_audios": [
                    {
                        "text": audio.example_text,
                        "audio": audio.audio_blob,
                        "tts_model": audio.tts_model
                    }
                    for audio in example_audios
                ]
            } 
