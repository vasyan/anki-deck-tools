# Architecture Overview

This diagram shows the complete system architecture with all modules and their relationships.

```mermaid
graph TB
    subgraph "Entry Points"
        CLI[main.py<br/>CLI Entry Point]
        API[api.py<br/>FastAPI Web Server]
        EMBED_CLI[embedding_cli.py<br/>Embedding CLI]
    end
    
    subgraph "Core Application Layer"
        APP[core/app.py<br/>AnkiVectorApp<br/>• Main orchestration<br/>• Delegates to services<br/>• Unified interface]
    end
    
    subgraph "Business Logic Layer"
        CARD_SVC[services/card_service.py<br/>CardService<br/>• Sync decks from Anki<br/>• Store/update cards<br/>• Handle Anki operations]
        
        EMBED_SVC[services/embedding_service.py<br/>EmbeddingService<br/>• Generate embeddings<br/>• Vector search<br/>• ML operations<br/>• Statistics]
    end
    
    subgraph "Data Access Layer"
        DB_MGR[database/manager.py<br/>DatabaseManager<br/>• Connection management<br/>• SQLite-vec setup<br/>• CRUD operations<br/>• Session handling]
        
        ANKI_CLIENT[anki/client.py<br/>AnkiConnectClient<br/>• HTTP client<br/>• Anki API calls<br/>• Error handling<br/>• Async operations]
    end
    
    subgraph "AI/ML Processing"
        EMBED_PROC[embedding_processor.py<br/>EmbeddingManager<br/>• Load ML models<br/>• Generate vectors<br/>• Batch processing<br/>• Similarity search]
    end
    
    subgraph "Data Models"
        DB_MODELS[models/database.py<br/>SQLAlchemy Models<br/>• AnkiCard<br/>• VectorEmbedding<br/>• Relationships]
        
        API_MODELS[models/schemas.py<br/>Pydantic Models<br/>• Request/Response<br/>• Validation<br/>• Serialization]
    end
    
    subgraph "External Systems"
        ANKI_APP[Anki Desktop<br/>AnkiConnect Plugin]
        SQLITE_DB[(SQLite Database<br/>+ sqlite-vec extension)]
        ML_MODELS[HuggingFace Models<br/>sentence-transformers]
    end
    
    CLI --> APP
    API --> APP
    EMBED_CLI --> APP
    
    APP --> CARD_SVC
    APP --> EMBED_SVC
    
    CARD_SVC --> DB_MGR
    CARD_SVC --> ANKI_CLIENT
    
    EMBED_SVC --> DB_MGR
    EMBED_SVC --> EMBED_PROC
    
    EMBED_PROC --> DB_MGR
    EMBED_PROC --> ML_MODELS
    
    DB_MGR --> DB_MODELS
    DB_MGR --> SQLITE_DB
    
    API --> API_MODELS
    
    ANKI_CLIENT --> ANKI_APP
    
    style CLI fill:#e1f5fe
    style API fill:#e1f5fe
    style EMBED_CLI fill:#e1f5fe
    style APP fill:#f3e5f5
    style CARD_SVC fill:#e8f5e8
    style EMBED_SVC fill:#e8f5e8
    style DB_MGR fill:#fff3e0
    style ANKI_CLIENT fill:#fff3e0
    style EMBED_PROC fill:#fff8e1
    style DB_MODELS fill:#fce4ec
    style API_MODELS fill:#fce4ec
```

## Key Components

### Entry Points
- **CLI (main.py)**: Command-line interface for basic operations
- **API (api.py)**: FastAPI web server providing REST endpoints
- **Embedding CLI**: Specialized CLI for embedding operations

### Core Application
- **AnkiVectorApp**: Main orchestration class that coordinates all operations
- Provides unified interface for different entry points
- Delegates work to specialized services

### Business Logic Services
- **CardService**: Handles all card-related operations (sync, storage, updates)
- **EmbeddingService**: Manages AI/ML operations (generation, search, statistics)

### Data Access Layer
- **DatabaseManager**: Handles SQLite connections, transactions, and sqlite-vec setup
- **AnkiConnectClient**: HTTP client for communicating with Anki Desktop

### AI/ML Processing
- **EmbeddingManager**: Loads ML models, generates vectors, performs similarity search

### Data Models
- **Database Models**: SQLAlchemy ORM models for data persistence
- **API Schemas**: Pydantic models for API request/response validation

### External Systems
- **Anki Desktop**: Source of card data via AnkiConnect plugin
- **SQLite Database**: Local storage with sqlite-vec extension for vector search
- **HuggingFace Models**: Pre-trained sentence transformers for embeddings 
