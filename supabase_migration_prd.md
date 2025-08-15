# **Supabase Migration Plan - Production Ready**
## **Limited Scope: 4 Tables + Binary Data In-Database**

Based on requirements analysis and research, this document outlines the migration plan for moving specific tables from SQLite to Supabase PostgreSQL while preserving binary data storage patterns.

## **Binary Data Research Findings**

✅ **PostgreSQL/Supabase CAN store binary data directly in database:**
- **BYTEA column limit**: 1GB per column (sufficient for audio files)
- **Supabase supports BYTEA**: No restrictions beyond PostgreSQL limits  
- **Audio file sizes**: TTS files typically 50KB-2MB (well within limits)
- **Performance**: BYTEA is efficient for files under 20MB

## **Migration Scope**

**Tables to migrate:**
1. `rankings` 
2. `learning_content`
3. `content_fragments` 
4. `fragment_assets` (with binary data preserved in BYTEA)

**Tables staying in SQLite:**
- `anki_cards` (external Anki integration)
- `vector_embeddings` (sqlite-vec dependency)

## **Architecture Strategy**

### **Hybrid Database Approach**
```python
# config.py - Updated
class Settings(BaseSettings):
    # SQLite for Anki/Vector operations  
    sqlite_database_url: str = Field(default="sqlite:///anki_vector_db.db")
    
    # Supabase for content management
    supabase_url: str = Field(env="SUPABASE_URL")
    supabase_anon_key: str = Field(env="SUPABASE_ANON_KEY") 
    postgres_database_url: str = Field(env="DATABASE_URL")  # PostgreSQL connection
```

## **Schema Migration**

### **1. Learning Content**
```sql
-- Supabase PostgreSQL schema
CREATE TABLE learning_content (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    content_type VARCHAR(50) NOT NULL,
    language VARCHAR(10) NOT NULL DEFAULT 'thai',
    native_text TEXT NOT NULL,
    translation TEXT NOT NULL, 
    ipa TEXT NOT NULL,
    difficulty_level INTEGER,
    tags JSONB,                    -- SQLite JSON -> PostgreSQL JSONB
    content_metadata JSONB,        -- Better JSON querying capabilities  
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes (enhanced with PostgreSQL features)
CREATE INDEX idx_learning_content_type ON learning_content(content_type);
CREATE INDEX idx_learning_content_language ON learning_content(language);
CREATE INDEX idx_learning_content_title ON learning_content(title);
CREATE INDEX idx_learning_content_tags ON learning_content USING GIN(tags);  -- JSONB index
CREATE INDEX idx_learning_content_metadata ON learning_content USING GIN(content_metadata);
```

### **2. Content Fragments**
```sql
CREATE TABLE content_fragments (
    id SERIAL PRIMARY KEY,
    native_text TEXT NOT NULL,
    body_text TEXT NOT NULL,
    ipa TEXT,
    extra TEXT,
    fragment_type VARCHAR(50) NOT NULL,
    fragment_metadata JSONB,       -- Enhanced JSON capabilities
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    learning_content_id INTEGER REFERENCES learning_content(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_fragment_type ON content_fragments(fragment_type);
CREATE INDEX idx_fragment_text ON content_fragments(native_text);
CREATE INDEX idx_fragment_content ON content_fragments(learning_content_id);
```

### **3. Fragment Assets (Key Change: Keep BYTEA)**
```sql
CREATE TABLE fragment_assets (
    id SERIAL PRIMARY KEY,
    fragment_id INTEGER REFERENCES content_fragments(id) ON DELETE CASCADE,
    asset_type VARCHAR(20) NOT NULL CHECK (asset_type IN ('audio', 'image', 'video')),
    asset_data BYTEA NOT NULL,     -- Keep binary data in database!
    asset_metadata JSONB,          -- Enhanced metadata storage
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100)
);

-- Indexes
CREATE INDEX idx_fragment_asset_type ON fragment_assets(fragment_id, asset_type);
CREATE INDEX idx_fragment_asset_created ON fragment_assets(created_at);
```

### **4. Rankings** 
```sql  
CREATE TABLE rankings (
    id SERIAL PRIMARY KEY,
    fragment_id INTEGER REFERENCES content_fragments(id) ON DELETE CASCADE,
    asset_id INTEGER REFERENCES fragment_assets(id) ON DELETE CASCADE,
    rank_score DECIMAL(3,2) DEFAULT 0.0 CHECK (rank_score >= 0.0 AND rank_score <= 5.0),
    assessed_by VARCHAR(100) NOT NULL,
    assessment_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes  
CREATE INDEX idx_rankings_fragment ON rankings(fragment_id);
CREATE INDEX idx_rankings_asset ON rankings(asset_id);
CREATE INDEX idx_rankings_score ON rankings(rank_score DESC);
```

## **Database Manager Strategy**

### **Dual Database Manager**
```python
# database/hybrid_manager.py
class HybridDatabaseManager:
    def __init__(self):
        # SQLite for Anki/Vectors
        self.sqlite_manager = DatabaseManager()  # Existing
        
        # PostgreSQL for content
        self.postgres_url = settings.postgres_database_url
        self.pg_engine = create_engine(self.postgres_url)
        self.PgSession = sessionmaker(bind=self.pg_engine)
    
    @contextmanager  
    def get_postgres_session(self):
        session = self.PgSession()
        try:
            yield session
        finally:
            session.close()
            
    @contextmanager
    def get_sqlite_session(self):
        return self.sqlite_manager.get_session()
```

## **Service Layer Updates**

### **Learning Content Service**
```python
# services/learning_content_service.py - Updated
class LearningContentService:
    def __init__(self):
        self.db_manager = HybridDatabaseManager()
    
    def create_content(self, payload: LearningContentCreate) -> int:
        with self.db_manager.get_postgres_session() as session:  # Use PostgreSQL
            # Same logic, different session
            learning_content = LearningContent(**payload.model_dump())
            session.add(learning_content)
            session.commit()
            return learning_content.id
```

### **Fragment Asset Manager** 
```python
# services/fragment_asset_manager.py - Key Update
class FragmentAssetManager:
    def __init__(self):
        self.db_manager = HybridDatabaseManager()
    
    async def store_asset(self, fragment_id: int, asset_data: bytes, 
                         asset_type: str, metadata: Dict = None) -> int:
        with self.db_manager.get_postgres_session() as session:
            asset = FragmentAsset(
                fragment_id=fragment_id,
                asset_type=asset_type, 
                asset_data=asset_data,  # Store directly in BYTEA - NO CHANGE!
                asset_metadata=metadata or {}
            )
            session.add(asset)
            session.commit()
            return asset.id
    
    def get_asset_data(self, asset_id: int) -> bytes:
        with self.db_manager.get_postgres_session() as session:
            asset = session.get(FragmentAsset, asset_id)
            return asset.asset_data  # Direct binary data access
```

## **Cross-Database Operations**

### **AnkiBuilder Workflow Updates**
```python
# workflows/anki_builder.py - Key Integration Points  
class AnkiBuilder:
    def __init__(self):
        self.card_service = CardService()  # Still uses SQLite
        self.lc_service = LearningContentService()  # Now uses PostgreSQL
        self.fragment_service = FragmentService()  # Now uses PostgreSQL
        
    async def process_sync(self, learning_content_id: int):
        # Get content from PostgreSQL
        rendered_content = await self.get_rendered_content(learning_content_id)
        
        # Sync to Anki via SQLite
        await self.card_service.sync_learning_content_to_anki(...)
```

## **Migration Process**

### **Step 1: Export SQLite Data**
```python
# scripts/export_sqlite_data.py
class DataExporter:
    def export_learning_content(self) -> List[Dict]:
        with sqlite_manager.get_session() as session:
            contents = session.query(LearningContent).all()
            return [self._serialize_content(c) for c in contents]
    
    def export_fragments_with_assets(self) -> List[Dict]:
        # Export fragments and their binary assets together
        with sqlite_manager.get_session() as session:
            fragments = session.query(ContentFragment).options(
                selectinload(ContentFragment.assets)
            ).all()
            return [self._serialize_fragment_with_assets(f) for f in fragments]
```

### **Step 2: Import to PostgreSQL**
```python 
# scripts/import_postgres_data.py
class DataImporter:
    def import_learning_content(self, data: List[Dict]):
        with postgres_manager.get_session() as session:
            for item in data:
                content = LearningContent(**item)
                session.add(content)
            session.commit()
    
    def import_fragments_with_binary_assets(self, data: List[Dict]):
        # Binary data transfers directly to BYTEA columns
        with postgres_manager.get_session() as session:
            for fragment_data in data:
                fragment = ContentFragment(...)
                session.add(fragment)
                session.flush()  # Get fragment ID
                
                # Import assets with binary data  
                for asset_data in fragment_data['assets']:
                    asset = FragmentAsset(
                        fragment_id=fragment.id,
                        asset_data=asset_data['binary_data'],  # Direct BYTEA
                        ...
                    )
                    session.add(asset)
            session.commit()
```

## **Key Benefits of This Approach**

### **1. Minimal Code Changes**
- **Asset handling**: No changes to binary data access patterns
- **Service layer**: Same interfaces, just different database sessions  
- **External integrations**: AnkiConnect continues unchanged

### **2. PostgreSQL Advantages for Content**
- **JSONB columns**: Better querying of metadata and tags
- **Better concurrency**: Multiple users can edit content simultaneously
- **Referential integrity**: CASCADE deletes for data consistency
- **Full-text search**: Built-in text search capabilities

### **3. Preserved Functionality**
- **Binary assets**: Continue storing audio files directly in database
- **Vector search**: Keep using sqlite-vec for embeddings  
- **Anki integration**: No changes to card syncing workflow

## **Environment Configuration**

### **Required Environment Variables**
```bash
# .env additions
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
DATABASE_URL=postgresql://postgres:[password]@db.xxx.supabase.co:5432/postgres

# Keep existing SQLite for hybrid approach
SQLITE_DATABASE_URL=sqlite:///anki_vector_db.db
```

### **Dependencies**
```bash
# Add to requirements.txt
psycopg2-binary>=2.9.0
supabase>=1.0.0
```

## **Timeline & Risk Assessment**

**Estimated timeline: 1-2 weeks**
- **Day 1-3**: Schema creation and hybrid database manager
- **Day 4-6**: Service layer updates and testing
- **Day 7-8**: Data migration scripts
- **Day 9-10**: Integration testing and deployment

**Low risk factors:**
- **Binary storage**: Proven PostgreSQL BYTEA capability 
- **Limited scope**: Only 4 tables, no external storage complexity
- **Preserved interfaces**: Service layer APIs remain the same
- **Gradual rollout**: Can test with subset of data first

## **Migration Steps Summary**

1. **Setup Supabase project** and obtain connection credentials
2. **Create PostgreSQL schemas** for the 4 target tables
3. **Implement HybridDatabaseManager** class
4. **Update service layer** to use appropriate database sessions
5. **Create data export/import scripts**
6. **Test with subset of data** to validate functionality
7. **Perform full migration** during maintenance window
8. **Update production configuration** to use hybrid approach

This approach gives you PostgreSQL benefits for content management while maintaining your preferred binary data storage pattern and existing integrations.