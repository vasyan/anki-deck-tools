import logging

from typing import Dict, Literal, Optional, Any, cast


from database.manager import DatabaseManager
from models.database import ContentFragment, FragmentAsset
from services.text_to_voice import TextToSpeechService
from models.schemas import FragmentAssetRowSchema

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class FragmentAssetManager:
    """Service for managing fragment assets and their rankings"""

    SUPPORTED_ASSET_TYPES = ['audio', 'image', 'video']

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.text_to_voice_service = TextToSpeechService()

    async def get_asset_by_fragment_id(
            self,
            fragment_id: int,
            type: Literal['audio', 'image', 'video'] = 'audio',
            generate_if_not_found: bool = False,
        ) -> Optional[FragmentAssetRowSchema]:
        with self.db_manager.get_session() as session:
            asset = session.query(FragmentAsset).filter(
                FragmentAsset.fragment_id == fragment_id,
                FragmentAsset.asset_type == type
            ).order_by(FragmentAsset.created_at.desc()).first()

            # If an asset already exists, verify it is still up to date with the fragment text.
            # We treat the asset as stale when the owning fragment was updated after the asset was generated.
            if asset:
                fragment = session.get(ContentFragment, fragment_id)

                # Safety-check: fragment should exist because of the FK, but guard anyway.
                if fragment:
                    from datetime import datetime, timezone

                    # Extract actual datetimes (SQLAlchemy Columns may confuse the type checker)
                    frag_updated: Optional[datetime] = getattr(fragment, "updated_at", None)  # type: ignore[attr-defined]
                    asset_created: Optional[datetime] = getattr(asset, "created_at", None)  # type: ignore[attr-defined]

                    if frag_updated and asset_created and frag_updated > asset_created:
                        # Fragment text was modified after the asset was generated → regenerate the asset so that
                        # the media matches the latest fragment content.
                        text_to_voice_result = await self.text_to_voice_service.synthesize(text=cast(str, fragment.native_text))

                        # Use setattr to avoid static-typing complaints about SQLAlchemy instrumentation
                        setattr(asset, "asset_data", text_to_voice_result.audio)
                        setattr(asset, "asset_metadata", {"tts_model": text_to_voice_result.tts_model})

                        # Force the ORM to pick up the change in timestamp to reflect regeneration time.
                        setattr(asset, "created_at", datetime.now(timezone.utc))

                        session.commit()

                return FragmentAssetRowSchema.model_validate(asset, from_attributes=True)

            # No asset exists → create one if allowed.
            if generate_if_not_found:
                fragment = session.get(ContentFragment, fragment_id)
                if fragment:
                    text_to_voice_result = await self.text_to_voice_service.synthesize(text=cast(str, fragment.native_text))
                    new_asset = self.create_asset(
                        fragment_id,
                        type,
                        text_to_voice_result.audio,
                        {"tts_model": text_to_voice_result.tts_model},
                    )
                    return new_asset
                return None

            return None


    def create_asset(
            self,
            fragment_id: int,
            type: Literal['audio', 'image', 'video'],
            data: bytes,
            metadata: Dict[str, Any],
        ) -> FragmentAssetRowSchema:
        with self.db_manager.get_session() as session:
            asset = FragmentAsset(fragment_id=fragment_id, asset_type=type, asset_data=data, asset_metadata=metadata)
            session.add(asset)

            session.commit()
            session.refresh(asset)

            return FragmentAssetRowSchema.model_validate(asset, from_attributes=True)
