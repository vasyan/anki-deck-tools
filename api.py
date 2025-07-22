"""
FastAPI server for the Anki Vector application
"""
import json
import logging
from typing import List, Dict, Any, Generator, Optional
from contextlib import asynccontextmanager
import asyncio
import uuid
from pathlib import Path
import os

from fastapi import FastAPI, HTTPException, Depends, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from core.app import AnkiVectorApp
from database.manager import DatabaseManager
from models.schemas import AnkiCardResponse, VectorSearchRequest, SyncCardRequest
from models.database import AnkiCard
from services.example_generator import ExampleGeneratorService
from services.fragment_manager import FragmentManager
from services.fragment_asset_manager import FragmentAssetManager
from services.template_parser import TemplateParser
from services.content_renderer import ContentRenderer
from services.learning_content_service import LearningContentService
from services.export_service import ExportService
from config import settings

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

# Initialize app and database
app_instance = AnkiVectorApp()
db_manager = DatabaseManager()

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Task storage for background processes (use Redis in production)
task_storage: Dict[str, Dict] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    logger.info("Starting Anki Vector API server")
    yield
    logger.info("Shutting down Anki Vector API server")

# FastAPI app
app = FastAPI(
    title="Anki Vector API",
    description="API for managing Anki cards with vector embeddings",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Dependency to get database session
def get_db() -> Generator[Session, None, None]:
    """Get database session"""
    with db_manager.get_session() as session:
        yield session

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Anki Vector API is running"}

# Sync endpoints
@app.post("/sync/deck")
async def sync_deck(request: SyncCardRequest) -> Dict[str, Any]:
    """Sync specific deck from Anki"""
    if not request.deck_names or len(request.deck_names) != 1:
        raise HTTPException(status_code=400, detail="Must provide exactly one deck name")
    
    deck_name = request.deck_names[0]
    try:
        result = await app_instance.sync_deck(deck_name)
        return result
    except Exception as e:
        logger.error(f"Error syncing deck {deck_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sync/all")
async def sync_all_decks() -> Dict[str, Any]:
    """Sync all decks from Anki"""
    try:
        result = await app_instance.sync_all_decks()
        return result
    except Exception as e:
        logger.error(f"Error syncing all decks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Card endpoints  
@app.get("/cards/deck", response_model=List[AnkiCardResponse])
async def get_cards_by_deck(deck_name: str) -> List[AnkiCardResponse]:
    """Get all cards for a specific deck"""
    try:
        cards = await db_manager.get_cards_by_deck(deck_name)
        return [
            AnkiCardResponse(
                id=card.id,
                anki_note_id=card.anki_note_id,
                deck_name=card.deck_name,
                model_name=card.model_name,
                front_text=card.front_text,
                back_text=card.back_text,
                tags=card.tags if card.tags else [],
                created_at=card.created_at,
                updated_at=card.updated_at,
                is_draft=getattr(card, 'is_draft', 1),
                example=getattr(card, 'example', None)
            )
            for card in cards
        ]
    except Exception as e:
        logger.error(f"Error getting cards for deck {deck_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cards", response_model=List[AnkiCardResponse])
async def get_all_cards(limit: int = 100, offset: int = 0) -> List[AnkiCardResponse]:
    """Get all cards with pagination"""
    try:
        with db_manager.get_session() as session:
            cards = session.query(AnkiCard).offset(offset).limit(limit).all()
            return [
                AnkiCardResponse(
                    id=card.id,
                    anki_note_id=card.anki_note_id,
                    deck_name=card.deck_name,
                    model_name=card.model_name,
                    front_text=card.front_text,
                    back_text=card.back_text,
                    tags=card.tags if card.tags else [],
                    created_at=card.created_at,
                    updated_at=card.updated_at,
                    is_draft=getattr(card, 'is_draft', 1),
                    example=getattr(card, 'example', None)
                )
                for card in cards
            ]
    except Exception as e:
        logger.error(f"Error getting all cards: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cards/{card_id}/audio")
async def get_card_audio(card_id: int):
	"""Return the audio for a card as an audio file (e.g., mp3)"""
	with db_manager.get_session() as session:
		card = session.get(AnkiCard, card_id)
		if not card or not card.audio:
			raise HTTPException(status_code=404, detail="Card or audio not found")
		# Default to mp3, could be made dynamic if needed
		return Response(card.audio, media_type="audio/mpeg")

# Embedding endpoints
@app.post("/embeddings/generate")
async def generate_embeddings(
    request: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Generate embeddings for specified cards"""
    try:
        card_ids = request.get("card_ids") if request else None
        force_regenerate = request.get("force_regenerate", False) if request else False
        
        result = await app_instance.generate_embeddings(
            card_ids=card_ids, 
            force_regenerate=force_regenerate
        )
        return result
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/embeddings/generate/deck/{deck_name}")
async def generate_embeddings_for_deck(
    deck_name: str, 
    force_regenerate: bool = False
) -> Dict[str, Any]:
    """Generate embeddings for all cards in a specific deck"""
    try:
        result = await app_instance.generate_embeddings(
            deck_name=deck_name, 
            force_regenerate=force_regenerate
        )
        return result
    except Exception as e:
        logger.error(f"Error generating embeddings for deck {deck_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/embeddings/generate/all")
async def generate_embeddings_for_all_decks(force_regenerate: bool = False) -> Dict[str, Any]:
    """Generate embeddings for all cards in all decks"""
    try:
        result = await app_instance.generate_embeddings_for_all_decks(force_regenerate=force_regenerate)
        return result
    except Exception as e:
        logger.error(f"Error generating embeddings for all decks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/embeddings/search")
async def search_similar_cards(request: VectorSearchRequest) -> List[Dict[str, Any]]:
    """Search for similar cards using vector similarity"""
    try:
        results = await app_instance.search_similar_cards(request)
        return results
    except Exception as e:
        logger.error(f"Error searching similar cards: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/embeddings/search/{deck_name}")
async def search_similar_cards_in_deck(
    deck_name: str,
    query_text: str,
    embedding_type: str = "combined",
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """Search for similar cards within a specific deck"""
    try:
        request = VectorSearchRequest(
            query_text=query_text,
            deck_name=deck_name,
            embedding_type=embedding_type,
            top_k=top_k
        )
        results = await app_instance.search_similar_cards(request)
        return results
    except Exception as e:
        logger.error(f"Error searching similar cards in deck {deck_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/embeddings/stats")
async def get_embedding_statistics() -> Dict[str, Any]:
    """Get detailed embedding statistics"""
    try:
        result = await app_instance.get_embedding_statistics()
        return result
    except Exception as e:
        logger.error(f"Error getting embedding statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Admin interface endpoints
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Main admin dashboard"""
    return templates.TemplateResponse("admin/dashboard.html", {"request": request})

@app.get("/admin/example", response_class=HTMLResponse)
async def admin_example(request: Request):
    """Example generation admin page"""
    return templates.TemplateResponse("admin/example_form.html", {"request": request})

@app.get("/admin/fragments", response_class=HTMLResponse)
async def admin_fragments(request: Request):
    """Fragment management admin page"""
    return templates.TemplateResponse("admin/fragments.html", {"request": request})

@app.get("/admin/learning-content", response_class=HTMLResponse)
async def admin_learning_content(request: Request):
    """Learning content management admin page"""
    return templates.TemplateResponse("admin/learning_content.html", {"request": request})

@app.get("/admin/example/instructions")
async def list_instruction_files():
    """List available instruction template files"""
    try:
        instructions_dir = Path("instructions")
        if not instructions_dir.exists():
            return {"files": []}
        
        files = []
        for file_path in instructions_dir.glob("*.txt"):
            files.append({
                "name": file_path.name,
                "path": str(file_path),
                "size": file_path.stat().st_size
            })
        
        return {"files": files}
    except Exception as e:
        logger.error(f"Error listing instruction files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/example/decks")
async def list_available_decks():
    """List available decks for selection"""
    try:
        with db_manager.get_session() as session:
            # Get distinct deck names from the database
            decks = session.query(AnkiCard.deck_name).distinct().all()
            deck_names = [deck[0] for deck in decks if deck[0]]  # Filter out None values
            
            return {
                "decks": sorted(deck_names),
                "total_count": len(deck_names)
            }
    except Exception as e:
        logger.error(f"Error listing available decks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/example/preview")
async def preview_example_generation(
    deck: str = Form(None),
    columns: str = Form(...),
    instructions_file: str = Form(...),
    limit: int = Form(5),  # Preview limit
    card_id: int = Form(None)  # Specific card ID for testing
):
    """Preview example generation with sample cards"""
    try:
        # Validate instruction file exists
        instructions_path = Path(instructions_file)
        if not instructions_path.exists():
            raise HTTPException(status_code=400, detail="Instruction file not found")
        
        # Read instruction template
        with open(instructions_path, 'r', encoding='utf-8') as f:
            template_str = f.read()
        
        # Parse columns
        columns_list = [c.strip() for c in columns.split(',')]
        
        # Get sample cards
        with db_manager.get_session() as session:
            query = session.query(AnkiCard)
            
            # If card_id is specified, only get that specific card
            if card_id:
                query = query.filter(AnkiCard.id == card_id)
                sample_cards = query.all()
            else:
                # Otherwise use deck filter and limit
                if deck:
                    query = query.filter(AnkiCard.deck_name == deck)
                
                # Get cards without examples for preview
                query = query.filter((AnkiCard.example == None) | (AnkiCard.example == ''))
                sample_cards = query.limit(limit).all()
        
        if not sample_cards:
            return {"preview_results": [], "message": "No cards available for preview"}
        
        # Generate preview examples
        example_service = ExampleGeneratorService()
        preview_results = []
        
        for card in sample_cards:
            try:
                # Get card data for specified columns
                card_data = {}
                for col in columns_list:
                    if hasattr(card, col):
                        card_data[col] = getattr(card, col)
                    else:
                        card_data[col] = None
                
                # Generate example
                generated_example = example_service.generate_example(card_data, template_str)
                
                preview_results.append({
                    "card_id": card.id,
                    "deck_name": card.deck_name,
                    "card_data": card_data,
                    "generated_example": generated_example,
                    "status": "success"
                })
                
            except Exception as e:
                preview_results.append({
                    "card_id": card.id,
                    "deck_name": card.deck_name,
                    "card_data": card_data,
                    "generated_example": None,
                    "error": str(e),
                    "status": "error"
                })
        
        return {
            "preview_results": preview_results,
            "total_cards": len(sample_cards),
            "template": template_str[:200] + "..." if len(template_str) > 200 else template_str
        }
        
    except Exception as e:
        logger.error(f"Error previewing example generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/example/start")
async def start_example_generation(
    deck: str = Form(None),
    columns: str = Form(...),
    instructions_file: str = Form(...),
    limit: int = Form(None),
    parallel: bool = Form(False),
    dry_run: bool = Form(False),
    card_id: int = Form(None)  # Specific card ID for testing
):
    """Start example generation process"""
    try:
        # Validate instruction file exists
        instructions_path = Path(instructions_file)
        if not instructions_path.exists():
            raise HTTPException(status_code=400, detail="Instruction file not found")
        
        # Create task
        task_id = str(uuid.uuid4())
        task_storage[task_id] = {
            "task_id": task_id,
            "status": "started",
            "progress": 0,
            "message": "🤖 Starting example generation...",
            "deck": deck,
            "columns": columns,
            "instructions_file": instructions_file,
            "limit": limit,
            "parallel": parallel,
            "dry_run": dry_run,
            "card_id": card_id,
            "result": None
        }
        
        # Start background task
        asyncio.create_task(run_example_generation_task(task_id))
        
        return {
            "task_id": task_id,
            "status": "started",
            "message": "Example generation started"
        }
        
    except Exception as e:
        logger.error(f"Error starting example generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/example/status/{task_id}")
async def get_example_generation_status(task_id: str):
    """Get status of example generation task"""
    task = task_storage.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "task_id": task_id,
        "status": task["status"],
        "progress": task["progress"],
        "message": task["message"],
        "result": task.get("result")
    }

@app.get("/admin/example/results/{task_id}")
async def get_example_generation_results(task_id: str):
    """Get results of completed example generation task"""
    task = task_storage.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")
    
    return task.get("result", {})

async def run_example_generation_task(task_id: str):
    """Background task for example generation"""
    task = task_storage[task_id]
    
    try:
        # Update status
        task["status"] = "running"
        task["progress"] = 10
        task["message"] = "📊 Loading cards and template..."
        
        # Read instruction template
        with open(task["instructions_file"], 'r', encoding='utf-8') as f:
            template_str = f.read()
        
        # Parse columns
        columns_list = [c.strip() for c in task["columns"].split(',')]
        
        # Get cards to process
        with db_manager.get_session() as session:
            query = session.query(AnkiCard)
            
            # If card_id is specified, only process that specific card
            if task["card_id"]:
                query = query.filter(AnkiCard.id == task["card_id"])
                cards = query.all()
            else:
                # Otherwise use deck filter and limit
                if task["deck"]:
                    query = query.filter(AnkiCard.deck_name == task["deck"])
                
                # Only process cards where example is empty
                query = query.filter((AnkiCard.example == None) | (AnkiCard.example == ''))
                
                if task["limit"]:
                    query = query.limit(task["limit"])
                
                cards = query.all()
        
        if not cards:
            task["status"] = "completed"
            task["progress"] = 100
            task["message"] = "✅ No cards found for processing"
            task["result"] = {
                "processed_cards": 0,
                "successful": 0,
                "failed": 0,
                "total_time": 0,
                "dry_run": task["dry_run"]
            }
            return
        
        # Update progress
        task["progress"] = 20
        if task["card_id"]:
            task["message"] = f"🔄 Processing card ID {task['card_id']}..."
        else:
            task["message"] = f"🔄 Processing {len(cards)} cards..."
        
        # Initialize example service
        example_service = ExampleGeneratorService()
        
        # Process cards
        successful = 0
        failed = 0
        failed_cards = []
        dry_run_results = []
        
        import time
        start_time = time.time()
        
        if task["parallel"]:
            # Parallel processing
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = []
                for card in cards:
                    future = executor.submit(process_single_card, card, columns_list, template_str, example_service, task["dry_run"])
                    futures.append((card, future))
                
                for i, (card, future) in enumerate(futures):
                    try:
                        result = future.result()
                        if result["success"]:
                            successful += 1
                            if task["dry_run"]:
                                dry_run_results.append({
                                    "card_id": card.id,
                                    "deck_name": card.deck_name,
                                    "front_text": card.front_text[:100] + "..." if len(card.front_text) > 100 else card.front_text,
                                    "generated_example": result["example"]
                                })
                        else:
                            failed += 1
                            failed_cards.append({
                                "card_id": card.id,
                                "error": result["error"]
                            })
                    except Exception as e:
                        failed += 1
                        failed_cards.append({
                            "card_id": card.id,
                            "error": str(e)
                        })
                    
                    # Update progress
                    progress = 20 + int(((i + 1) / len(cards)) * 70)
                    task["progress"] = progress
                    task["message"] = f"🔄 Processed {i + 1} of {len(cards)} cards..."
        else:
            # Sequential processing
            for i, card in enumerate(cards):
                try:
                    result = process_single_card(card, columns_list, template_str, example_service, task["dry_run"])
                    if result["success"]:
                        successful += 1
                        if task["dry_run"]:
                            dry_run_results.append({
                                "card_id": card.id,
                                "deck_name": card.deck_name,
                                "front_text": card.front_text[:100] + "..." if len(card.front_text) > 100 else card.front_text,
                                "generated_example": result["example"]
                            })
                    else:
                        failed += 1
                        failed_cards.append({
                            "card_id": card.id,
                            "error": result["error"]
                        })
                except Exception as e:
                    failed += 1
                    failed_cards.append({
                        "card_id": card.id,
                        "error": str(e)
                    })
                
                # Update progress
                progress = 20 + int(((i + 1) / len(cards)) * 70)
                task["progress"] = progress
                task["message"] = f"🔄 Processed {i + 1} of {len(cards)} cards..."
        
        # Final update
        end_time = time.time()
        processing_time = end_time - start_time
        
        task["status"] = "completed"
        task["progress"] = 100
        task["message"] = f"✅ Example generation completed! Success: {successful}, Failed: {failed}"
        task["result"] = {
            "processed_cards": len(cards),
            "successful": successful,
            "failed": failed,
            "failed_cards": failed_cards,
            "processing_time": processing_time,
            "dry_run": task["dry_run"],
            "dry_run_results": dry_run_results if task["dry_run"] else []
        }
        
        logger.info(f"Example generation completed. Task: {task_id}, Success: {successful}, Failed: {failed}")
        
    except Exception as e:
        task["status"] = "error"
        task["progress"] = -1
        task["message"] = f"❌ Error: {str(e)}"
        logger.error(f"Example generation task failed: {e}")

def process_single_card(card, columns_list, template_str, example_service, dry_run):
    """Process a single card for example generation"""
    try:
        # Get card data for specified columns
        card_data = {}
        for col in columns_list:
            if hasattr(card, col):
                card_data[col] = getattr(card, col)
            else:
                card_data[col] = None
        
        # Generate example
        generated_example = example_service.generate_example(card_data, template_str)
        
        # Save to database unless dry run
        if not dry_run:
            with db_manager.get_session() as session:
                db_card = session.get(AnkiCard, card.id)
                if db_card:
                    db_card.example = generated_example
                    session.commit()
        
        return {
            "success": True,
            "example": generated_example
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# Stats endpoints
@app.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """Get database statistics"""
    try:
        with db_manager.get_session() as session:
            total_cards = session.query(AnkiCard).count()
            deck_counts = {}
            
            # Get card count per deck
            decks = session.query(AnkiCard.deck_name).distinct().all()
            for (deck_name,) in decks:
                count = session.query(AnkiCard).filter_by(deck_name=deck_name).count()
                deck_counts[deck_name] = count
            
            return {
                "total_cards": total_cards,
                "total_decks": len(deck_counts),
                "deck_counts": deck_counts
            }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Fragment Management API Endpoints

@app.post("/fragments")
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

@app.get("/fragments/types")
async def get_fragment_types():
    """Get all supported fragment types"""
    try:
        fragment_manager = FragmentManager()
        return fragment_manager.get_fragment_types()
    except Exception as e:
        logger.error(f"Error getting fragment types: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/fragments/stats")
async def get_fragment_stats():
    """Get fragment statistics"""
    try:
        fragment_manager = FragmentManager()
        return fragment_manager.get_fragment_statistics()
    except Exception as e:
        logger.error(f"Error getting fragment stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/fragments")
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

@app.get("/fragments/{fragment_id}")
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

@app.put("/fragments/{fragment_id}")
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

@app.delete("/fragments/{fragment_id}")
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

@app.post("/fragments/{fragment_id}/assets")
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

@app.get("/fragments/{fragment_id}/assets")
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

@app.put("/fragments/assets/{asset_id}/activate")
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

@app.put("/fragments/assets/{asset_id}/assess")
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

@app.delete("/fragments/assets/{asset_id}")
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

@app.get("/fragments/assets/stats")
async def get_fragment_asset_stats():
    """Get fragment asset statistics"""
    try:
        asset_manager = FragmentAssetManager()
        return asset_manager.get_asset_statistics()
    except Exception as e:
        logger.error(f"Error getting fragment asset stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Template and Content Rendering API Endpoints

@app.post("/templates/parse")
async def parse_template(template_content: str = Form(...)):
    """Parse template content and extract fragment tokens"""
    try:
        parser = TemplateParser()
        tokens = parser.parse_template(template_content)
        
        return {
            "tokens": tokens,
            "fragment_count": len(set(token['fragment_id'] for token in tokens))
        }
    except Exception as e:
        logger.error(f"Error parsing template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/templates/render")
async def render_template(
    template_content: str = Form(...),
    output_format: str = Form("html"),
    card_id: int = Form(None),
    track_usage: bool = Form(True)
):
    """Render template content"""
    try:
        parser = TemplateParser()
        rendered_content = parser.render_template(template_content, output_format, card_id, track_usage)
        
        return {
            "rendered_content": rendered_content,
            "original_content": template_content,
            "output_format": output_format
        }
    except Exception as e:
        logger.error(f"Error rendering template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/templates/validate")
async def validate_template(template_content: str = Form(...)):
    """Validate template content"""
    try:
        parser = TemplateParser()
        validation = parser.validate_template(template_content)
        
        return validation
    except Exception as e:
        logger.error(f"Error validating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cards/{card_id}/render")
async def render_card_content(card_id: int, output_format: str = "html"):
    """Render all content for a card"""
    try:
        renderer = ContentRenderer()
        rendered = renderer.render_card_content(card_id, output_format)
        
        return rendered
    except Exception as e:
        logger.error(f"Error rendering card content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cards/{card_id}/fragments")
async def get_card_fragments(card_id: int):
    """Get fragments used by a card"""
    try:
        renderer = ContentRenderer()
        summary = renderer.get_card_fragments_summary(card_id)
        
        return summary
    except Exception as e:
        logger.error(f"Error getting card fragments: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cards/{card_id}/convert")
async def convert_legacy_card(card_id: int, auto_generate_audio: bool = Form(False)):
    """Convert legacy card content to fragment system"""
    try:
        renderer = ContentRenderer()
        
        # Get TTS service if needed
        tts_service = None
        if auto_generate_audio:
            from services.text_to_voice import TextToSpeechService
            tts_service = TextToSpeechService()
        
        result = renderer.convert_legacy_examples(card_id, auto_generate_audio, tts_service)
        
        return result
    except Exception as e:
        logger.error(f"Error converting card: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cards/{card_id}/preview")
async def preview_card_rendering(card_id: int):
    """Preview how a card would render in different formats"""
    try:
        renderer = ContentRenderer()
        preview = renderer.preview_card_rendering(card_id)
        
        return preview
    except Exception as e:
        logger.error(f"Error previewing card: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Learning Content API Endpoints

@app.get("/api/learning-content/stats")
async def get_learning_content_stats():
    """Get learning content statistics"""
    try:
        learning_service = LearningContentService()
        
        content_types = learning_service.get_content_types()
        languages = learning_service.get_languages()
        
        return {
            'content_types': content_types,
            'languages': languages
        }
    except Exception as e:
        logger.error(f"Error getting learning content stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/learning-content")
async def get_learning_content(
    page: int = 1,
    page_size: int = 20,
    content_type: Optional[str] = None,
    language: Optional[str] = None,
    search: Optional[str] = None
):
    """Get learning content with filtering and pagination"""
    try:
        learning_service = LearningContentService()
        
        filters = {}
        if content_type:
            filters['content_type'] = content_type
        if language:
            filters['language'] = language
        if search:
            filters['text_search'] = search
            
        result = learning_service.search_content(filters, page, page_size)
        return result
    except Exception as e:
        logger.error(f"Error getting learning content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/learning-content/{content_id}")
async def get_learning_content_by_id(content_id: int):
    """Get specific learning content by ID"""
    try:
        learning_service = LearningContentService()
        content = learning_service.get_content(content_id)
        
        if not content:
            raise HTTPException(status_code=404, detail="Learning content not found")
            
        return content
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting learning content {content_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/learning-content/{content_id}")
async def update_learning_content(content_id: int, updates: Dict[str, Any]):
    """Update learning content"""
    try:
        learning_service = LearningContentService()
        success = learning_service.update_content(content_id, **updates)
        
        if not success:
            raise HTTPException(status_code=404, detail="Learning content not found")
            
        return {"success": True, "message": f"Learning content {content_id} updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating learning content {content_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/learning-content/{content_id}/export/{format}")
async def export_learning_content(content_id: int, format: str):
    """Export learning content to different formats"""
    try:
        export_service = ExportService()
        
        if format == 'anki':
            result = export_service.export_to_anki(content_id)
        elif format == 'api-json':
            result = export_service.export_to_api_json(content_id)
        elif format == 'html':
            result = export_service.export_to_html(content_id)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported export format: {format}")
            
        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting learning content {content_id} to {format}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    ) 
