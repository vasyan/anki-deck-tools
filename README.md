# Anki Vector Database

A Python application for managing Anki flashcard data with vector embeddings and semantic search capabilities.

## Features

- **Anki Integration**: Sync cards from Anki via AnkiConnect
- **Vector Embeddings**: Generate semantic embeddings for card content using sentence transformers
- **Semantic Search**: Find similar cards using vector similarity
- **SQLite Storage**: Efficient storage with sqlite-vec extension for vector operations
- **REST API**: FastAPI-based HTTP interface
- **CLI Tools**: Command-line interface for batch operations

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment** (optional):
   ```bash
   cp env.example .env
   # Edit .env with your settings
   ```

3. **Start AnkiConnect**: 
   - Install AnkiConnect addon in Anki
   - Keep Anki running during sync operations

## Quick Start

### Sync Cards from Anki
```bash
python main.py  # Starts the API server
# Use API endpoints or sync via the web interface
```

### Generate Embeddings

**Using the standalone CLI:**
```bash
# Generate embeddings for all decks
python embedding_cli.py --generate --all-decks

# Generate embeddings for a specific deck
python embedding_cli.py --generate --deck "My Deck Name"

# View statistics
python embedding_cli.py --stats

# Search for similar cards
python embedding_cli.py --search "your search query" --top-k 5
```

**Using the processor directly:**
```bash
# Generate for all decks
python embedding_processor.py --all-decks

# Generate for specific deck
python embedding_processor.py --deck "My Deck Name"

# Search similar cards
python embedding_processor.py --search "your query" --top-k 10
```

### Configuration Options

The embedding system supports various configuration options via environment variables:

```bash
# Model configuration
EMBEDDING_MODEL=all-MiniLM-L6-v2  # Sentence transformer model
EMBEDDING_BATCH_SIZE=32           # Batch size for processing
EMBEDDING_DEVICE=auto             # Device: auto, cpu, cuda, mps
EMBEDDING_CACHE_DIR=./models      # Model cache directory

# Database
DATABASE_URL=sqlite:///anki_vector_db.db

# AnkiConnect
ANKI_CONNECT_URL=http://localhost:8765
```

## Embedding Types

The system generates three types of embeddings for each card:

- **front**: Embedding of the front text only
- **back**: Embedding of the back text only  
- **combined**: Embedding of front + back text combined

## API Endpoints

- `GET /cards` - List all cards
- `POST /sync/deck/{deck_name}` - Sync specific deck
- `POST /sync/all` - Sync all decks
- `POST /search/similar` - Search for similar cards

## Architecture

- **main.py**: Core application, database models, AnkiConnect client
- **embedding_processor.py**: Embedding generation and management
- **embedding_cli.py**: Standalone CLI for embedding operations
- **config.py**: Configuration management
- **api.py**: FastAPI HTTP endpoints

## Performance Notes

- **Apple Silicon**: Automatically uses MPS acceleration when available
- **CUDA**: Supports GPU acceleration on compatible systems
- **Batch Processing**: Efficient batch processing for large decks
- **Caching**: Text embeddings are cached to avoid recomputation
- **No Regeneration**: By default, existing embeddings are not regenerated

## Error Handling

The system uses simple error handling as requested:
- Errors are logged with detailed context about which task failed
- Processing continues for other cards/decks when individual items fail
- CLI provides clear error messages with task information

## Example Usage

```bash
# First, sync your cards from Anki
python main.py &  # Start API server
curl -X POST http://localhost:8000/sync/all

# Generate embeddings
python embedding_cli.py --generate --all-decks

# Search for similar cards
python embedding_cli.py --search "vocabulary word" --embedding-type combined --top-k 5

# View statistics
python embedding_cli.py --stats
```

This will download the sentence transformer model (~91MB) on first use and generate embeddings for all your cards.

## Dependencies

Key dependencies include:
- sentence-transformers: For embedding generation
- torch: ML framework (supports CPU, CUDA, MPS)
- sqlite-vec: Vector operations in SQLite
- fastapi: Web API framework
- sqlalchemy: Database ORM

## Project Structure

```
anki-vector-app/
├── main.py              # Core application logic
├── api.py               # FastAPI server
├── config.py            # Configuration management
├── requirements.txt     # Dependencies
├── env.example         # Environment template
└── README.md           # This file
```

## Troubleshooting

### AnkiConnect Issues
- Ensure Anki is running and AnkiConnect plugin is installed
- Check if `localhost:8765` is accessible
- Verify AnkiConnect version compatibility

### Database Issues
- Ensure sqlite-vec extension is properly installed
- Check database permissions and file paths

### Vector Storage
- SQLite vector storage is ready for production
- Mock embeddings are in place for testing
- Replace with actual embedding models as needed

## License

MIT License 
