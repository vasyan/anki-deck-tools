"""
FastAPI server for the Anki Vector application
"""
import json
import logging
from typing import List, Dict, Any, Generator
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
async def example_generation_form(request: Request):
    """Example generation form"""
    return templates.TemplateResponse("admin/example_form.html", {"request": request})

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

@app.post("/admin/example/preview")
async def preview_example_generation(
    deck: str = Form(None),
    columns: str = Form(...),
    instructions_file: str = Form(...),
    limit: int = Form(5)  # Preview limit
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
    dry_run: bool = Form(False)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    ) 
