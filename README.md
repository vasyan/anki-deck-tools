# Anki Vector Data Management System (MVP)

A Python application that synchronizes Anki flashcards and stores them with vector embeddings for semantic search and analysis.

## Features

- **Anki Integration**: Connect to Anki via AnkiConnect plugin
- **Vector Storage**: Store embeddings in SQLite with sqlite-vec extension
- **HTTP API**: FastAPI-based REST API for data management
- **Async Support**: Fully asynchronous operations using httpx and asyncio
- **Mock Embeddings**: Ready for actual embedding model integration

## Prerequisites

1. **Anki with AnkiConnect**:
   - Install Anki
   - Install AnkiConnect plugin (code: `2055492159`)
   - Restart Anki and keep it running

2. **Python 3.8+**

## Quick Start

1. **Setup**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configuration**:
   ```bash
   cp env.example .env
   # Edit .env with your settings
   ```

3. **Test the setup**:
   ```bash
   python main.py
   ```

4. **Run API server**:
   ```bash
   python api.py
   # Or: uvicorn api:app --reload
   ```

5. **Install HTTPie** (optional, for easier API testing):
   ```bash
   pip install httpie
   # Or: brew install httpie (macOS)
   # Or: apt install httpie (Ubuntu/Debian)
   ```

## API Endpoints

- `GET /health` - Health check
- `POST /sync/deck` - Sync specific deck (JSON body)
- `POST /sync/all` - Sync all decks
- `GET /cards/deck?deck_name=<name>` - Get cards by deck
- `GET /cards` - Get all cards (paginated)
- `POST /embeddings/generate` - Generate embeddings
- `POST /embeddings/search` - Vector similarity search (mock)
- `GET /stats` - Database statistics

## Database Schema

### AnkiCard
- `id` - Primary key
- `anki_note_id` - Unique Anki note ID
- `deck_name` - Name of the deck
- `model_name` - Anki note model
- `front_text` - Front side text
- `back_text` - Back side text
- `tags` - JSON array of tags
- `created_at` / `updated_at` - Timestamps

### VectorEmbedding
- `id` - Primary key
- `card_id` - Foreign key to AnkiCard
- `embedding_type` - Type ('front', 'back', 'combined')
- `vector_data` - JSON stored embedding
- `vector_dimension` - Embedding dimension
- `created_at` - Timestamp

### Vector Search Table (sqlite-vec)
- `id` - Primary key
- `card_id` - Reference to card
- `embedding_type` - Type of embedding
- `vector` - BLOB format for efficient search

## Usage Examples

*HTTPie provides cleaner syntax than curl - especially useful for JSON APIs and testing. Both examples are provided below.*

### Sync specific deck
```bash
# curl
curl -X POST http://localhost:8000/sync/deck \
  -H "Content-Type: application/json" \
  -d '{"deck_names": ["Japanese Grammar"]}'

# HTTPie
http POST localhost:8000/sync/deck deck_names:='["Japanese Grammar"]'
```

### Sync all decks
```bash
# curl
curl -X POST http://localhost:8000/sync/all

# HTTPie  
http POST localhost:8000/sync/all
```

### Generate embeddings (mock)
```bash
# curl
curl -X POST http://localhost:8000/embeddings/generate

# HTTPie
http POST localhost:8000/embeddings/generate
```

### Search cards by deck
```bash
# curl
curl "http://localhost:8000/cards/deck?deck_name=Japanese%20Grammar"

# HTTPie
http GET localhost:8000/cards/deck deck_name=="Japanese Grammar"
```

### Vector search (mock)
```bash
# curl
curl -X POST http://localhost:8000/embeddings/search \
  -H "Content-Type: application/json" \
  -d '{"query_text": "hello", "top_k": 5}'

# HTTPie
http POST localhost:8000/embeddings/search query_text="hello" top_k:=5
```

### Get database stats
```bash
# curl
curl http://localhost:8000/stats

# HTTPie
http GET localhost:8000/stats
```

## Next Steps

1. **Replace mock embeddings** with actual models:
   - sentence-transformers
   - OpenAI embeddings
   - Custom models

2. **Implement real vector search** using sqlite-vec functions

3. **Add authentication** for production use

4. **Optimize performance** with proper indexing

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
