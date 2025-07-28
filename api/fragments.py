import logging
from fastapi import APIRouter, Form, HTTPException
# from typing import Dict, Any, List
from database.manager import DatabaseManager
from database.manager import DatabaseManager
import logging
import json
from services.fragment_asset_manager import FragmentAssetManager

from services.fragment_manager import FragmentManager

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
        fragment_manager = FragmentManager()
        
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
        fragment_manager = FragmentManager()
        return fragment_manager.get_fragment_types()
    except Exception as e:
        logger.error(f"Error getting fragment types: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fragments/stats")
async def get_fragment_stats():
    """Get fragment statistics"""
    try:
        fragment_manager = FragmentManager()
        return fragment_manager.get_fragment_statistics()
    except Exception as e:
        logger.error(f"Error getting fragment stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fragments")
async def search_fragments(
    text_search: str = None,
    fragment_type: str = None,
    has_assets: bool = None,
    limit: int = 50,
    offset: int = 0
):
    """Search fragments"""
    try:
        fragment_manager = FragmentManager()
        fragments = fragment_manager.find_fragments(text_search, fragment_type, has_assets, limit, offset)
        
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
        fragment_manager = FragmentManager()
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
        fragment_manager = FragmentManager()
        
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
        fragment_manager = FragmentManager()
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
    asset_type: str = None,
    active_only: bool = False
):
    """Get assets for a fragment"""
    try:
        asset_manager = FragmentAssetManager()
        assets = asset_manager.get_fragment_assets(fragment_id, asset_type, active_only)
        
        # Remove binary data from response for JSON serialization
        for asset in assets:
            if 'asset_data' in asset:
                asset['asset_data_size'] = len(asset['asset_data'])
                del asset['asset_data']
        
        return {"assets": assets}
    except Exception as e:
        logger.error(f"Error getting assets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/fragments/assets/{asset_id}/activate")
async def activate_asset(asset_id: int, is_active: bool = Form(True)):
    """Activate or deactivate an asset"""
    try:
        asset_manager = FragmentAssetManager()
        success = asset_manager.set_asset_active(asset_id, is_active)
        
        if not success:
            raise HTTPException(status_code=404, detail="Asset not found")
        
        return {"message": f"Asset {'activated' if is_active else 'deactivated'} successfully"}
    except Exception as e:
        logger.error(f"Error activating asset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/fragments/assets/{asset_id}/assess")
async def assess_asset(
    asset_id: int,
    rank_score: float = Form(...),
    assessed_by: str = Form(...),
    assessment_notes: str = Form(None),
    set_active: bool = Form(None)
):
    """Assess an asset quality"""
    try:
        asset_manager = FragmentAssetManager()
        success = asset_manager.assess_asset(asset_id, rank_score, assessed_by, assessment_notes, set_active)
        
        if not success:
            raise HTTPException(status_code=404, detail="Asset not found")
        
        return {"message": "Asset assessed successfully"}
    except Exception as e:
        logger.error(f"Error assessing asset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/fragments/assets/{asset_id}")
async def delete_asset(asset_id: int):
    """Delete an asset"""
    try:
        asset_manager = FragmentAssetManager()
        success = asset_manager.delete_asset(asset_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Asset not found")
        
        return {"message": "Asset deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting asset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fragments/assets/stats")
async def get_fragment_asset_stats():
    """Get fragment asset statistics"""
    try:
        asset_manager = FragmentAssetManager()
        return asset_manager.get_asset_statistics()
    except Exception as e:
        logger.error(f"Error getting fragment asset stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
