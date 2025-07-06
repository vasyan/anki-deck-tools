# Anki Vector Application - Architecture Documentation

This directory contains Mermaid diagrams that illustrate the architecture and workflows of the Anki Vector application.

## 📋 Available Diagrams

### 1. [Architecture Overview](./architecture-overview.md)
Complete system architecture showing all modules, their relationships, and dependencies.

### 2. [Card Synchronization Flow](./card-sync-flow.md)
Sequence diagram showing how cards are synchronized from Anki Desktop to the local database.

### 3. [Embedding Generation Flow](./embedding-generation-flow.md)
Sequence diagram illustrating the process of generating AI embeddings for cards.

### 4. [Vector Search Flow](./vector-search-flow.md)
Sequence diagram showing how vector similarity search works to find related cards.

### 5. [Layered Architecture](./layered-architecture.md)
Architectural layers diagram showing the separation of concerns and clean architecture principles.

## 🎯 How to Use These Diagrams

1. **View in GitHub**: GitHub natively renders Mermaid diagrams in markdown files
2. **Local Rendering**: Use tools like:
   - [Mermaid Live Editor](https://mermaid.live/)
   - VS Code with Mermaid extension
   - Obsidian with Mermaid plugin
3. **Export**: Convert to PNG/SVG using mermaid-cli or online tools

## 📖 Understanding the Architecture

The diagrams show a clean, modular architecture with:
- **Separation of Concerns**: Each module has a single responsibility
- **Dependency Injection**: Services receive their dependencies
- **Clean Interfaces**: Layers only depend on layers below them
- **Async Operations**: Non-blocking I/O throughout the system

## 🔧 Key Components

- **Entry Points**: CLI, FastAPI, embedding CLI
- **Core App**: Main orchestration (`AnkiVectorApp`)
- **Services**: Business logic (Card sync, Embedding operations)
- **Infrastructure**: Database, Anki client, ML processing
- **Models**: Data definitions and API schemas
- **Storage**: SQLite with sqlite-vec extension

## 🚀 Main Workflows

1. **Card Sync**: Anki Desktop → AnkiConnect → CardService → Database
2. **Embedding Generation**: Cards → ML Models → Vector Database
3. **Vector Search**: Query → Embeddings → Similarity Search → Results 
