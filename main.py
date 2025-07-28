import logging
from typing import Dict, Any, Generator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database.manager import DatabaseManager
from models.database import AnkiCard
from config import settings
from api.sync import router as sync_router
from api.embedding import router as embedding_router
from api.fragments import router as fragments_router
from api.templates import router as templates_router
from api.cards import router as cards_router
from api.learning_content import router as learning_content_router
from api.admin import router as admin_router

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

db_manager = DatabaseManager()

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

# Mount routers
app.include_router(sync_router)
app.include_router(embedding_router)
app.include_router(fragments_router)
app.include_router(templates_router)
app.include_router(cards_router)
app.include_router(learning_content_router)
app.include_router(admin_router)

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


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(
#         "main:app",
#         host=settings.api_host,
#         port=settings.api_port,
#         reload=True
#     ) 
