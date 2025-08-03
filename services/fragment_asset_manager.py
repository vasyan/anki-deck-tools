import logging

from typing import Dict, Literal, Optional, Any, cast
from datetime import datetime, timezone

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
                    # Extract actual datetimes (SQLAlchemy Columns may confuse the type checker)
                    frag_updated: Optional[datetime] = getattr(fragment, "updated_at", None)  # type: ignore[attr-defined]
                    asset_created: Optional[datetime] = getattr(asset, "created_at", None)  # type: ignore[attr-defined]

                    if frag_updated and asset_created and frag_updated > asset_created:
                        # Fragment text was modified after the asset was generated → regenerate the asset
                        return await self.generate_asset_for_fragment(fragment_id, type, existing_asset_id=cast(int, asset.id))

                return FragmentAssetRowSchema.model_validate(asset, from_attributes=True)

            # No asset exists → create one if allowed.
            if generate_if_not_found:
                fragment = session.get(ContentFragment, fragment_id)
                if fragment:
                    return await self.generate_asset_for_fragment(fragment_id, type)
                return None

            return None

    async def generate_asset_for_fragment(
            self,
            fragment_id: int,
            asset_type: Literal['audio', 'image', 'video'],
            existing_asset_id: Optional[int] = None,
        ) -> FragmentAssetRowSchema:
        """Generate or regenerate an asset for a fragment"""
        with self.db_manager.get_session() as session:
            fragment = session.get(ContentFragment, fragment_id)
            if not fragment:
                raise ValueError(f"Fragment with id {fragment_id} not found")

            text_to_voice_result = await self.text_to_voice_service.synthesize(text=cast(str, fragment.native_text))

            if existing_asset_id:
                # Update existing asset
                existing_asset = session.get(FragmentAsset, existing_asset_id)
                if not existing_asset:
                    raise ValueError(f"Asset with id {existing_asset_id} not found")

                setattr(existing_asset, "asset_data", text_to_voice_result.audio)
                setattr(existing_asset, "asset_metadata", {"tts_model": text_to_voice_result.tts_model})
                setattr(existing_asset, "created_at", datetime.now(timezone.utc))
                session.commit()
                return FragmentAssetRowSchema.model_validate(existing_asset, from_attributes=True)
            else:
                # Create new asset
                new_asset = FragmentAsset(
                    fragment_id=fragment_id,
                    asset_type=asset_type,
                    asset_data=text_to_voice_result.audio,
                    asset_metadata={"tts_model": text_to_voice_result.tts_model}
                )
                session.add(new_asset)
                session.commit()
                session.refresh(new_asset)
                return FragmentAssetRowSchema.model_validate(new_asset, from_attributes=True)

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

    def get_asset(self, asset_id: int) -> Optional[Dict[str, Any]]:
        """Get an asset by ID, including its binary data"""
        with self.db_manager.get_session() as session:
            asset = session.get(FragmentAsset, asset_id)

            if not asset:
                return None

            # Convert to dict to include binary data that might not be in Pydantic model
            return {
                "id": asset.id,
                "fragment_id": asset.fragment_id,
                "asset_type": asset.asset_type,
                "asset_data": asset.asset_data,
                "asset_metadata": asset.asset_metadata,
                "created_at": asset.created_at
            }

    def get_fragment_assets(self, fragment_id: int, asset_type: Optional[str] = None, active_only: bool = False) -> list[Dict[str, Any]]:
        """Get all assets for a fragment"""
        with self.db_manager.get_session() as session:
            query = session.query(FragmentAsset).filter(FragmentAsset.fragment_id == fragment_id)

            if asset_type:
                query = query.filter(FragmentAsset.asset_type == asset_type)

            # Order by creation date, newest first
            query = query.order_by(FragmentAsset.created_at.desc())

            assets = query.all()

            # Convert to dict to include binary data
            return [
                {
                    "id": asset.id,
                    "fragment_id": asset.fragment_id,
                    "asset_type": asset.asset_type,
                    "asset_data": asset.asset_data,
                    "asset_metadata": asset.asset_metadata,
                    "created_at": asset.created_at
                }
                for asset in assets
            ]
