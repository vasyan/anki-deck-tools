# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an Anki flashcard management system with AI-powered enhancements for Thai language learning. It uses FastAPI, SQLite with vector extensions, and integrates with Anki Desktop via AnkiConnect.

## Development Commands

### Environment Setup
```bash
# Activate conda environment (required)
conda activate anki-thai

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Start the FastAPI server
python main.py
# OR
uvicorn main:app --reload --port 8000

# Access points
# Web interface: http://localhost:8000/admin
# API docs: http://localhost:8000/docs
```

**IMPORTANT FOR AI ASSISTANTS**: 
- NEVER run `python main.py` or start the FastAPI server
- NEVER run `python test.py` with any arguments - this script can potentially break the database
- The server is always running in the background during development
- Only use read-only commands for testing (curl, browser access, etc.)

### Testing and Type Checking
```bash
# Run workflow tests
python test.py fragments  # Test fragment processing
python test.py contents   # Test content processing
python test.py upload     # Test Anki upload

# Type checking (strict mode enabled)
mypy .
pyright .
```

### CLI Tools
```bash
python cli/embedding_cli.py        # Generate embeddings
python cli/example_generator_cli.py # Generate AI examples
python cli/publish_cli.py          # Publish to Anki
```

## Architecture Overview

### Service Layer Pattern
All business logic is encapsulated in services under `/services/`:
- **CardService**: Anki card synchronization
- **LearningContentService**: Abstract content management with fragments
- **FragmentManager**: Reusable content fragments (basic_meaning, pronunciation_and_tone, real_life_example, usage_tip)
- **FragmentAssetManager**: Audio/media assets
- **EmbeddingService**: Vector embeddings using sentence-transformers
- **LLMService**: AI example generation via local LLM (port 1234)
- **TextToVoiceService**: OpenAI TTS integration

### Database Models
SQLAlchemy models in `/models/db.py`:
- **LearningContent**: Abstract learning items with Thai word/meaning
- **ContentFragment**: Reusable content pieces linked to learning content
- **FragmentAsset**: Binary assets (audio/image/video) with quality rankings
- **AnkiCard**: Synchronized Anki flashcards
- **VectorEmbedding**: ML embeddings for semantic search

### API Layer
FastAPI routers in `/api/` handle HTTP requests and delegate to services. Main routers:
- `admin.py`: Web interface dashboard
- `learning_content.py`: Content CRUD operations
- `fragments.py`: Fragment management
- `web.py`: New web API endpoints

### Workflow Layer
High-level business workflows in `/workflows/`:
- **AnkiBuilder**: Orchestrates the full pipeline from content → fragments → assets → Anki cards

## External Dependencies

### Required Services
- **Anki Desktop** with AnkiConnect plugin running
- **Local LLM Server** (LM Studio) on port 1234 for AI generation
- **OpenAI API** (optional) for TTS and advanced examples

### Configuration
Create `.env` file (copy from `env.example`) with:
- Database path configuration
- OpenAI API key (if using)
- LLM model selection

## Code Style Guidelines

From `.cursorrules`:
- Use type hints for all functions
- Prefer functional programming over OOP (except for external API clients)
- Use Pydantic models for structured data
- Handle exceptions explicitly
- Access database only through service layer
- Use `async/await` for all database operations

## Key Development Patterns

### Fragment System
Content is broken into reusable fragments with four types:
1. `basic_meaning`: Core definition
2. `pronunciation_and_tone`: Phonetic guide
3. `real_life_example`: Usage examples
4. `usage_tip`: Learning tips

### Template Rendering
Templates in `/services/card_template_service.py` render content for different export formats (Anki, JSON, HTML).

### Vector Search
Embeddings are generated using sentence-transformers and stored with sqlite-vec for semantic search capabilities.

## Testing Approach

The main test file `test.py` provides workflow testing. When adding new features:
1. Test services in isolation first
2. Add integration tests to workflow tests
3. Ensure type checking passes with `mypy` and `pyright`