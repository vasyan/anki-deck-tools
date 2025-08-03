from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from database.manager import DatabaseManager
from models.database import FragmentAsset

db_manager = DatabaseManager()

router = APIRouter()

@router.get("/assets/{asset_id}")
async def get_asset(asset_id: int):
	"""Return the audio for a card as an audio file (e.g., mp3)"""
	with db_manager.get_session() as session:
		asset = session.get(FragmentAsset, asset_id)
		if not asset:
			raise HTTPException(status_code=404, detail="Asset not found")
		return Response(asset.asset_data, media_type="audio/mpeg")
