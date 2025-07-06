# Anki Vector Application - Modular Architecture

## Overview

The application has been refactored from a monolithic `main.py` file into a clean, modular architecture that follows the Single Responsibility Principle and separation of concerns.

## New Directory Structure

```
anki-thai/
├── models/                    # Data models and schemas
│   ├── __init__.py           # Package exports
│   ├── database.py           # SQLAlchemy database models
│   └── schemas.py            # Pydantic API request/response models
├── database/                  # Database management
│   ├── __init__.py           # Package exports
│   └── manager.py            # DatabaseManager class with connection/operations
├── anki/                      # Anki integration
│   ├── __init__.py           # Package exports
│   └── client.py             # AnkiConnect client for Anki communication
├── services/                  # Business logic services
│   ├── __init__.py           # Package exports
│   ├── card_service.py       # Card synchronization operations
│   └── embedding_service.py  # Vector embedding operations
├── core/                      # Application orchestration
│   ├── __init__.py           # Package exports
│   └── app.py                # Main AnkiVectorApp orchestration class
├── config.py                 # Configuration settings (unchanged)
├── embedding_processor.py    # ML/AI processing (updated imports)
├── api.py                    # FastAPI web API (updated imports)
├── main.py                   # CLI entry point (simplified)
└── embedding_cli.py          # CLI for embeddings (unchanged)
```

## Architecture Benefits

### 1. **Separation of Concerns**
- **Models**: Pure data definitions (SQLAlchemy and Pydantic)
- **Database**: Data persistence and connection management
- **Anki**: External service integration
- **Services**: Business logic implementation
- **Core**: High-level application orchestration
- **API**: Web interface layer

### 2. **Dependency Injection**
- Services accept database manager instances
- Makes testing easier with mock dependencies
- Reduces tight coupling between components

### 3. **Import Hierarchy**
```
main.py (CLI) → core.app → services → database/anki/models
api.py (Web) → core.app → services → database/anki/models
embedding_processor.py → database → models
```

### 4. **No Circular Dependencies**
- Fixed the circular import between `main.py` and `embedding_processor.py`
- Clear dependency direction: higher-level modules depend on lower-level ones

## Key Classes and Responsibilities

### Core Application (`core/app.py`)
- **AnkiVectorApp**: Main orchestration class
- Delegates to specialized services
- Provides unified interface for both CLI and API

### Services (`services/`)
- **CardService**: Manages Anki card synchronization
- **EmbeddingService**: Handles vector embedding operations
- Each service focused on a specific business domain

### Database Layer (`database/manager.py`)
- **DatabaseManager**: Connection management, session handling
- SQLite-vec extension setup
- Card and embedding storage operations

### Models (`models/`)
- **database.py**: SQLAlchemy ORM models (`AnkiCard`, `VectorEmbedding`)
- **schemas.py**: Pydantic models for API validation

### Anki Integration (`anki/client.py`)
- **AnkiConnectClient**: HTTP client for AnkiConnect API
- Async context manager for connection handling

## Migration Benefits

1. **Maintainability**: Each module has a single, clear responsibility
2. **Testability**: Components can be tested in isolation
3. **Reusability**: Services can be reused across different interfaces (CLI, API, etc.)
4. **Scalability**: Easy to add new features or modify existing ones
5. **Code Organization**: Logical grouping makes the codebase easier to navigate

## Usage Examples

### Using the Application
```python
# CLI usage (main.py)
from core.app import AnkiVectorApp
app = AnkiVectorApp()
await app.sync_deck("My Deck")

# API usage (api.py) 
from core.app import AnkiVectorApp
app_instance = AnkiVectorApp()  # Used by FastAPI endpoints

# Direct service usage
from services.card_service import CardService
card_service = CardService()
await card_service.sync_deck("My Deck")
```

### Testing Individual Components
```python
# Test database operations
from database.manager import DatabaseManager
db = DatabaseManager("sqlite:///test.db")

# Test Anki client
from anki.client import AnkiConnectClient
async with AnkiConnectClient() as client:
    decks = await client.get_deck_names()

# Test services with mock dependencies
from services.card_service import CardService
service = CardService(mock_db_manager)
```

## Future Enhancements

The modular structure makes it easy to add:
- New embedding models (extend `services/embedding_service.py`)
- Different database backends (extend `database/manager.py`)
- Additional APIs (create new API modules importing from `core.app`)
- Monitoring and logging services
- Background task scheduling
- Plugin system for custom processors 
