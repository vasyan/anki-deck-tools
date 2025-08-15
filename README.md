# Anki Thai

A comprehensive flashcard management system for Thai language learning with AI-powered enhancements, vector search, and seamless Anki integration.

## Prerequisites

- Python 3.8 or higher
- Conda (Miniconda or Anaconda)
- Anki Desktop with AnkiConnect plugin installed
- LM Studio with Typhoon LLM model (for AI example generation)
- OpenAI API key (optional, for text-to-speech)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd anki-thai
```

### 2. Set Up Conda Environment

```bash
# Create and activate the conda environment
conda create -n anki-thai python=3.8
conda activate anki-thai
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
# Copy the example environment file
cp env.example .env

# Edit .env with your configuration
```

Required configuration in `.env`:
- `DATABASE_URL`: SQLite database path (default: `sqlite:///anki_vector_db.db`)
- `LM_STUDIO_API_BASE`: LM Studio API endpoint (default: `http://127.0.0.1:1234/v1`)
- `LOCAL_MODEL_THAI`: Model name for Thai content (default: `lm_studio/typhoon2.1-gemma3-4b-mlx`)
- `OPENAI_API_KEY`: Your OpenAI API key (optional, for TTS features)

## External Services Setup

### 1. Anki Desktop with AnkiConnect

1. Install Anki Desktop from https://apps.ankiweb.net/
2. Install the AnkiConnect plugin:
   - Open Anki → Tools → Add-ons → Get Add-ons
   - Enter code: `2055492159`
   - Restart Anki
3. Ensure Anki is running when using this application (AnkiConnect runs on port 8765)

### 2. LM Studio Setup

1. Download and install LM Studio from https://lmstudio.ai/
2. Download the Typhoon model:
   - Open LM Studio
   - Search for "typhoon2.1-gemma3-4b" or similar Thai-capable model
   - Download and load the model
3. Start the local server:
   - Go to Server tab in LM Studio
   - Click "Start Server" (runs on port 1234 by default)

### 3. Database Initialization

The SQLite database with vector extensions will be created automatically on first run. No manual setup required.

## Running the Application

### Start the FastAPI Server

```bash
# Activate the conda environment
conda activate anki-thai

# Start the server
python main.py

# Or use uvicorn directly
uvicorn main:app --reload --port 8000
```

### Access Points

- **Web Interface**: http://localhost:8000/admin
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Key Features

- **Learning Content Management**: Create and manage abstract learning content with Thai language support
- **Fragment System**: Reusable content fragments (meanings, pronunciation, examples, tips)
- **AI-Powered Generation**: Generate examples using local LLM (Typhoon) or OpenAI
- **Vector Search**: Semantic search using sentence-transformers embeddings
- **Audio Generation**: Text-to-speech synthesis for pronunciation
- **Anki Integration**: Seamless synchronization with Anki Desktop
- **Multiple Export Formats**: Export to Anki, JSON, or HTML
- **Web Admin Interface**: User-friendly dashboard for all operations

## Project Structure

```
anki-thai/
├── api/                # FastAPI routers
├── services/           # Business logic services
├── models/             # Database models and schemas
├── workflows/          # High-level business workflows
├── templates/          # HTML and Jinja2 templates
├── static/             # CSS and JavaScript files
├── cli/                # Command-line tools
├── database/           # Database management
└── main.py             # Application entry point
```

## Development

### Type Checking

```bash
# Run type checking
mypy .
pyright .
```

### Testing Workflows

```bash
# Test fragment processing
python test.py fragments

# Test content processing
python test.py contents

# Test Anki upload
python test.py upload
```

## CLI Tools

Additional command-line tools are available for advanced operations:

```bash
python cli/embedding_cli.py        # Generate embeddings
python cli/example_generator_cli.py # Generate AI examples
python cli/publish_cli.py          # Publish to Anki
```

## Troubleshooting

1. **AnkiConnect Connection Error**: Ensure Anki Desktop is running with the AnkiConnect plugin installed
2. **LM Studio Connection Error**: Verify LM Studio server is running on port 1234
3. **Database Lock Error**: Close any other connections to the SQLite database
4. **Import Errors**: Ensure the conda environment is activated and all dependencies are installed

## License

MIT License