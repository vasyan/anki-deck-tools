import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

from database.manager import DatabaseManager
from models.database import FragmentAsset, Ranking
from services.fragment_asset_manager import FragmentAssetManager

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

db_manager = DatabaseManager()
asset_manager = FragmentAssetManager()

router = APIRouter()

@router.get("/assets/{asset_id}")
async def get_asset(asset_id: int):
	"""Return the audio for a card as an audio file (e.g., mp3)"""
	with db_manager.get_session() as session:
		asset = session.get(FragmentAsset, asset_id)
		if not asset:
			raise HTTPException(status_code=404, detail="Asset not found")
		return Response(asset.asset_data, media_type="audio/mpeg")

class AssetRankingInput(BaseModel):
    rank_score: float
    assessment_notes: Optional[str] = None
    assessed_by: str = "admin"

@router.post("/assets/{asset_id}/ranking")
async def set_asset_ranking(asset_id: int, ranking_data: AssetRankingInput):
    """Set a ranking score for an asset

    Args:
        asset_id: ID of the asset to rank
        ranking_data: Ranking details including score, notes, and assessor

    Returns:
        The created or updated ranking
    """
    with db_manager.get_session() as session:
        logger.info(f"Setting ranking for asset {asset_id} with data {ranking_data}")
        # Check if asset exists
        asset = session.get(FragmentAsset, asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        try:
            # Get or create ranking
            existing_ranking = session.query(Ranking).filter(
                Ranking.asset_id == asset_id
            ).first()

            if existing_ranking:
                # Update existing ranking using setattr instead of direct assignment
                setattr(existing_ranking, "rank_score", ranking_data.rank_score)
                setattr(existing_ranking, "assessment_notes", ranking_data.assessment_notes)
                setattr(existing_ranking, "assessed_by", ranking_data.assessed_by)
                ranking_id = existing_ranking.id
            else:
                # Create new ranking
                new_ranking = Ranking(
                    asset_id=asset_id,
                    fragment_id=asset.fragment_id,
                    rank_score=ranking_data.rank_score,
                    assessment_notes=ranking_data.assessment_notes,
                    assessed_by=ranking_data.assessed_by
                )
                session.add(new_ranking)
                session.flush()
                ranking_id = new_ranking.id

            session.commit()

            # Retrieve the ranking after commit to get fresh data
            result = session.query(Ranking).get(ranking_id)

            if not result:
                raise HTTPException(status_code=404, detail="Ranking not found after creation")

            return {
                "id": result.id,
                "asset_id": result.asset_id,
                "fragment_id": result.fragment_id,
                "rank_score": result.rank_score,
                "assessed_by": result.assessed_by,
                "assessment_notes": result.assessment_notes
            }
        except Exception as e:
            session.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to create/update ranking: {str(e)}")
