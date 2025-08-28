# Anki Thai

A comprehensive flashcard management system for Thai language learning with AI-powered enhancements

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
conda create -n anki-thai python=3.13.4
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
- `OPENAI_API_KEY`: Your OpenAI API key ( actually it is optional for TTS features )

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

For quick setup with sample data, see the [Seed Data Guide](seed_data.md).

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

- **Web Admin Interface**: Dashboard for generated content review process
- **Fragment System**: Reusable content fragments (meanings, pronunciation, examples, tips)
- **AI-Powered Generation**: Generate examples using local LLM (Typhoon) or OpenAI
- **Audio Generation**: Text-to-speech synthesis for pronunciation
- **Anki Integration**: Seamless synchronization with Anki Desktop

## Project Structure

```
anki-thai/
├── api/                # FastAPI routers
├── services/           # Business logic services
├── models/             # Database models and schemas
├── workflows/          # High-level workflows to deal with generation/sync
├── templates/          # HTML and Jinja2 templates
├── cli/                # DEPRECATED! Command-line tools
├── database/           # Database management
└── main.py             # Application entry point
```

### Running worflows
Currently there is no flexible way to adjust requirements beside of changing the source code. However, mostly it means simple change selection filter/limit/etc

```bash
# Generate examples ( aka content_fragments ) for learning_contents
# IMPORTANT! you have to tweak the source code right in the `anki_builder.py` method `process_contents`
python run.py contents

# Generate voice for content_fragments ( aka examples )
# IMPORTANT! you have to tweak the source code right in the `anki_builder.py` method `process_fragments`
python run.py fragments

# Test Anki upload
# IMPORTANT! you have to tweak the source code right in the `anki_builder.py` method `sync_to_anki`
python run.py anki
```

## License

MIT License
