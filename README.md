# Anki Vector Database Project

A Python-based system for managing Anki flashcards with vector embeddings and AI-powered enhancements.

## Features

- **Learning Content Management**: Abstract content system with template-based approach supporting multiple export formats
- **Fragment System**: Reusable content fragments with audio assets and quality rankings
- **Multi-Format Export**: Export learning content to Anki, JSON (API), and HTML formats
- **Vector Embeddings**: Generate and search card embeddings using sentence transformers
- **AI Example Generation**: Create examples for cards using language models
- **Text-to-Speech**: Generate audio for cards using OpenAI's TTS
- **Card Management**: Sync cards from Anki, manage drafts, and publish to Anki
- **Web Interface**: User-friendly admin panel for managing all operations
- **REST API**: Full HTTP API for programmatic access

## Quick Start

### Prerequisites
This project uses **miniconda** for environment management. Make sure you have conda installed.

### Setup

1. **Activate the conda environment:**
   ```bash
   conda activate anki-thai
   ```

2. **Install dependencies (if not already done):**
   ```bash
   pip install -r requirements.txt
   ```

3. **Test the system:**
   ```bash
   python test_new_architecture.py
   ```

4. **Start the server:**
   ```bash
   python api.py
   # OR
   python -m uvicorn api:app --reload --port 8000
   ```

5. **Access the web interface:**
   Open `http://localhost:8000/admin` in your browser

## Web Interface

The web interface provides an intuitive way to:
- **Learning Content Management**: Create, edit, and organize abstract learning content (`/admin/learning-content`)
- **Fragment Management**: Manage reusable content fragments and audio assets (`/admin/fragments`)
- **Multi-Format Export**: Export content to Anki cards, API JSON, or standalone HTML
- Generate AI-powered examples for your cards
- Manage vector embeddings
- Create text-to-speech audio
- Publish draft cards to Anki
- Monitor processing progress in real-time

### Key Admin Interfaces:
- **Dashboard**: `http://localhost:8000/admin` - Main admin panel
- **Learning Content**: `http://localhost:8000/admin/learning-content` - Content management
- **Fragments**: `http://localhost:8000/admin/fragments` - Fragment system management

See [Web Interface Guide](docs/web-interface-guide.md) for detailed usage instructions.

## Command Line Interface

For advanced users, CLI tools are available:

- `python embedding_cli.py` - Manage vector embeddings
- `python example_generator_cli.py` - Generate examples via CLI
- `python tts_cli.py` - Generate text-to-speech audio
- `python publish_cli.py` - Publish draft cards to Anki

## API Documentation

When the server is running, visit `http://localhost:8000/docs` for interactive API documentation.

## Configuration

Copy `env.example` to `.env` and configure your settings:

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Database
DATABASE_URL=sqlite:///anki_vector_db.db

# OpenAI (for example generation and TTS)
OPENAI_API_KEY=your_openai_api_key_here

# Embedding Model
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

## Architecture

The system follows a layered architecture:

- **Web Interface**: Bootstrap-based admin panel with real-time updates
- **API Layer**: FastAPI with automatic OpenAPI documentation
- **Service Layer**: Business logic for embeddings, examples, and TTS
- **Data Layer**: SQLite with vector support and Anki integration

## Documentation

- [Architecture Overview](docs/architecture-overview.md)
- [Web Interface Guide](docs/web-interface-guide.md)
- [Card Sync Flow](docs/card-sync-flow.md)
- [Embedding Generation Flow](docs/embedding-generation-flow.md)
- [Vector Search Flow](docs/vector-search-flow.md)

## Recent Updates

### Web Interface (Latest)
- ✅ **Example Generation Web Interface**: Full-featured web UI for AI example generation
- ✅ **Real-time Progress Tracking**: Live progress updates with polling
- ✅ **Template Preview**: Preview generated examples before processing
- ✅ **Dry Run Mode**: Test templates without saving to database
- ✅ **Parallel Processing Control**: User-configurable parallel vs sequential processing
- ✅ **Smart Deck Selection**: Dropdown with available decks for easy selection
- ✅ **Card ID Testing**: Process specific cards by ID for precise testing
- ✅ **Error Handling**: Detailed error reporting and recovery options

### Previous Updates
- ✅ Vector embedding generation and search
- ✅ OpenAI integration for examples and TTS
- ✅ Anki card synchronization
- ✅ CLI tools for all operations
- ✅ REST API with full documentation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details. 
