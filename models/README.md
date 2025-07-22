# Database Models

This directory contains the database models for the Anki Thai application. The models are built using SQLAlchemy ORM and represent the different entities in the system.

## Model Overview

### Legacy Anki System

- **AnkiCard**: Represents traditional Anki flashcards with front and back text, audio, and examples.
- **VectorEmbedding**: Stores vector embeddings of cards for semantic search functionality.
- **ExampleAudioLog**: Tracks audio generation and publishing actions for card examples.

### Learning Content System

- **LearningContent**: The abstract learning content that can be exported to various platforms (like Anki).
  - Contains templates that can reference content fragments
  - Supports different content types (vocabulary, grammar, phrases)
  - Provides classification with difficulty levels and tags

### Content Fragment System

- **ContentFragment**: Reusable content pieces that can be shared across multiple learning content items.
  - Each fragment represents a specific piece of content (Thai word, phrase, explanation)
  - Fragments can be of different types and have metadata for organization

- **FragmentAsset**: Assets associated with content fragments, primarily audio files.
  - Multiple assets can be attached to a single fragment (different audio recordings)
  - Stores binary data and metadata about the asset

- **FragmentAssetRanking**: System for ranking and selecting the best assets for fragments.
  - Allows tracking which asset is currently active for a fragment
  - Supports quality ranking and assessment notes

- **FragmentLearningContentMap**: Maps content fragments to learning content items.
  - Tracks the status of fragments (active, pending, processing, unused)
  - Specifies how each fragment is associated with the learning content (front_text, example, etc.)
  - Provides extensibility through a metadata JSON field

## Relationships

1. **LearningContent → AnkiCard**: One-to-many relationship. Each learning content can be exported to multiple Anki cards.

2. **ContentFragment → FragmentAsset**: One-to-many relationship. Each content fragment can have multiple assets (different audio recordings).

3. **ContentFragment ↔ LearningContent**: Many-to-many relationship through the FragmentLearningContentMap table. A fragment can be used in multiple learning content items, and a learning content item can use multiple fragments.

4. **FragmentAsset → FragmentAssetRanking**: One-to-many relationship. Each asset can have multiple rankings.

## Data Flow

1. Content fragments are created with text and metadata
2. Assets (audio, images) are generated and attached to fragments
3. Learning content is created with templates referencing fragments
4. Fragment-to-learning content mappings are established with appropriate association types
5. Learning content is exported to Anki cards when needed

## Schema Design Principles

1. **Modularity**: The system separates content, assets, and learning materials for flexibility.
2. **Reusability**: Content fragments can be shared across multiple learning materials.
3. **Extensibility**: JSON metadata fields allow for future expansion without schema changes.
4. **Tracking**: All operations and relationships are tracked with timestamps and status fields. 
