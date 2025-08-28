# Seed Data Documentation

The `seed_data.json` file contains:
- **10 LearningContent records** - Thai vocabulary with translations and IPA pronunciation
- **76 ContentFragments** - Examples, pronunciation guides, usage tips
- **67 FragmentAssets** - Audio files for pronunciation (base64 encoded)
- **10 AnkiCards** - Pre-configured flashcards ready for Anki
- **Related rankings** - For search and quality metrics

## Importing Seed Data

### For New Installations

1. **Import the seed data**:
   ```bash
   # This creates a new database with seed data
   python import_seed_data.py --database sqlite:///anki_vector_db.db --clear
   ```

2. **Verify the import**:
   ```bash
   # Start the server
   DATABASE_URL=sqlite:///test_anki.db uvicorn main:app --reload --host 0.0.0.0 --port 8000

   # Visit http://localhost:8000/admin to see the imported content
   ```
