import logging
from fastapi import APIRouter, Form, HTTPException
from database.manager import DatabaseManager
from database.manager import DatabaseManager
import json
from models.schemas import ContentFragmentSearchRow, FragmentType, FragmentRankingInput
from services.fragment_asset_manager import FragmentAssetManager

from services.fragment_service import FragmentService

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

db_manager = DatabaseManager()


router = APIRouter()

@router.post("/fragments")
async def create_fragment(
    text: str = Form(...),
    fragment_type: str = Form(...),
    metadata: str = Form(None)
):
    """Create a new content fragment"""
    try:
        fragment_manager = FragmentService()

        # Parse metadata if provided
        parsed_metadata = {}
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metadata JSON")

        fragment_id = fragment_manager.create_fragment(text, fragment_type, parsed_metadata)

        return {
            "fragment_id": fragment_id,
            "message": "Fragment created successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating fragment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fragments/types")
async def get_fragment_types():
    """Get all supported fragment types"""
    try:
        fragment_manager = FragmentService()
        return fragment_manager.get_fragment_types()
    except Exception as e:
        logger.error(f"Error getting fragment types: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fragments/stats")
async def get_fragment_stats():
    """Get fragment statistics"""
    try:
        fragment_manager = FragmentService()
        return fragment_manager.get_fragment_statistics()
    except Exception as e:
        logger.error(f"Error getting fragment stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fragments")
async def search_fragments(
    text_search: str | None = None,
    fragment_type: FragmentType | None = None,
    has_assets: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    min_rating: float | None = None
):
    try:
        fragment_manager = FragmentService()
        fragments = fragment_manager.find_fragments(ContentFragmentSearchRow(
            text_search=text_search,
            fragment_type=fragment_type,
            has_assets=has_assets,
            limit=limit,
            offset=offset,
            min_rating=min_rating
        ))

        return {
            "fragments": fragments,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error searching fragments: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fragments/{fragment_id}")
async def get_fragment(fragment_id: int):
    """Get a fragment by ID"""
    try:
        fragment_manager = FragmentService()
        fragment = fragment_manager.get_fragment(fragment_id)

        if not fragment:
            raise HTTPException(status_code=404, detail="Fragment not found")

        return fragment
    except Exception as e:
        logger.error(f"Error getting fragment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/fragments/{fragment_id}")
async def update_fragment(
    fragment_id: int,
    text: str = Form(None),
    fragment_type: str = Form(None),
    metadata: str = Form(None)
):
    """Update a fragment"""
    try:
        fragment_manager = FragmentService()

        # Parse metadata if provided
        parsed_metadata = None
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metadata JSON")

        success = fragment_manager.update_fragment(fragment_id, text, fragment_type, parsed_metadata)

        if not success:
            raise HTTPException(status_code=404, detail="Fragment not found")

        return {"message": "Fragment updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating fragment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/fragments/{fragment_id}")
async def delete_fragment(fragment_id: int):
    """Delete a fragment"""
    try:
        fragment_manager = FragmentService()
        success = fragment_manager.delete_fragment(fragment_id)

        if not success:
            raise HTTPException(status_code=404, detail="Fragment not found")

        return {"message": "Fragment deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting fragment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Fragment Asset API Endpoints

@router.post("/fragments/{fragment_id}/assets")
async def add_fragment_asset(
    fragment_id: int,
    asset_type: str = Form(...),
    asset_file: bytes = Form(...),
    asset_metadata: str = Form(None),
    created_by: str = Form(None),
    auto_activate: bool = Form(True)
):
    """Add an asset to a fragment"""
    try:
        asset_manager = FragmentAssetManager()

        # Parse metadata if provided
        parsed_metadata = {}
        if asset_metadata:
            try:
                parsed_metadata = json.loads(asset_metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metadata JSON")

        asset_id = asset_manager.add_asset(
            fragment_id, asset_type, asset_file, parsed_metadata, created_by, auto_activate
        )

        return {
            "asset_id": asset_id,
            "message": "Asset added successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding asset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fragments/{fragment_id}/assets")
async def get_fragment_assets(
    fragment_id: int,
    asset_type: str | None = "audio"
):
    """Get assets for a fragment"""
    try:
        asset_manager = FragmentAssetManager()
        assets = asset_manager.get_fragment_assets_with_rankings(fragment_id, asset_type)

        # print(f"assets: {assets}")

        # Remove binary data from response for JSON serialization
        for asset in assets:
            if 'asset_data' in asset:
                asset['asset_data_size'] = len(asset['asset_data'])
                del asset['asset_data']

        return {"assets": assets}
    except Exception as e:
        logger.error(f"Error getting assets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fragments/assets/{asset_id}")
async def get_asset_data(asset_id: int):
    """Get the binary data for an asset"""
    try:
        asset_manager = FragmentAssetManager()
        asset = asset_manager.get_asset(asset_id)

        if not asset or 'asset_data' not in asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        from fastapi.responses import Response

        # Determine content type based on asset_type
        content_type = "audio/mpeg"  # Default for audio
        if asset.get('asset_type') == 'image':
            content_type = "image/jpeg"  # Adjust based on your image types

        return Response(
            content=asset['asset_data'],
            media_type=content_type
        )
    except Exception as e:
        logger.error(f"Error fetching asset data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fragments/{fragment_id}/learning-content")
async def get_fragment_learning_content(fragment_id: int):
    """Get learning content related to a fragment"""
    try:
        fragment_manager = FragmentService()
        learning_content = fragment_manager.get_fragment_learning_content(fragment_id)

        if not learning_content:
            return {"learning_content": []}

        return {"learning_content": learning_content}
    except Exception as e:
        logger.error(f"Error getting learning content for fragment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/fragments/{fragment_id}/generate-asset")
async def generate_asset_for_fragment(fragment_id: int):
    """Generate an asset for a fragment"""
    try:
        asset_manager = FragmentAssetManager()
        await asset_manager.generate_asset_for_fragment(fragment_id, 'audio')
        return {"message": "Asset generated successfully"}
    except Exception as e:
        logger.error(f"Error generating asset for fragment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/fragments/{fragment_id}/ranking")
async def set_fragment_ranking(fragment_id: int, ranking_data: FragmentRankingInput):
    """Set a ranking score for a fragment"""
    try:
        fragment_manager = FragmentService()
        ranking = fragment_manager.set_fragment_ranking(fragment_id, ranking_data)
        return ranking
    except Exception as e:
        logger.error(f"Error setting fragment ranking: {e}")
        raise HTTPException(status_code=500, detail=str(e))
