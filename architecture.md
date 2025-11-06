# Architecture Overview

## System Components

### 1. **React UI** (`timetable-ui/`)
- **Purpose**: Web frontend for file upload and timetable viewing
- **Tech**: React 19, TypeScript
- **Responsibilities**: File selection, upload trigger, result display, basic calendar view

### 2. **Node.js API** (`timetable-api/`)
- **Purpose**: REST API gateway and orchestrator
- **Tech**: Express, TypeScript, SQLite client
- **Responsibilities**: 
  - File upload handling (multipart/form-data)
  - Invoke Python processor as subprocess for extraction
  - Database query/retrieval
  - CORS-enabled (origin: *)

### 3. **Python Processor** (`src/processor/`)
- **Purpose**: Core data extraction engine
- **Tech**: Python 3.12+, PaddleOCR, img2table
- **Responsibilities**:
  - Document preprocessing (multi-format support: PNG, JPG, PDF, DOCX)
  - OCR extraction via PaddleOCR
  - Table detection and parsing
  - Structured data generation (JSON)
  - Database writes

### 4. **SQLite Database** (`db/timetable.sqlite`)
- **Purpose**: Persistent storage of processed timetables
- **Schema**:
  - `timetable_sources`: Metadata (file path, processed timestamp)
  - `extracted_activities`: Extracted rows (activity, day, time slots, notes)

---

## Data Flow

```
┌──────────────┐
│   React UI   │
│  (Browser)   │
└──────┬───────┘
       │ (1) File + POST /timetable/upload
       ▼
┌──────────────────────┐
│    Express API       │
│  (Node.js Server)    │
└────────┬─────────────┘
         │ (2) Save file to disk
         │ (3) Spawn Python subprocess
         ▼
    ┌────────────────────────┐
    │  Python Processor      │
    │  (Child Process)       │
    │                        │
    │ • Preprocess file      │
    │ • OCR extraction       │
    │ • Table detection      │
    │ • Parse timetable      │
    │ • DB write             │
    └────────────┬───────────┘
                 │ (4) Print JSON to stdout
                 ▼
         ┌──────────────┐
         │  SQLite DB   │
         │              │
         │ Sources      │
         │ Activities   │
         └──────────────┘
                 ▲
                 │ (5) Read results from Python
                 │ (6) Query DB for details
                 │
┌────────────────┴────────────────┐
│      API Response to UI           │
│  {                               │
│    sourceId, activities[],       │
│    extractionStatus              │
│  }                               │
└────────────────────────────────┘
                 ▲
                 │ (7) Display results
                 │
         ┌───────┴────────┐
         │  React UI      │
         │  (Calendar)    │
         └────────────────┘
```

---

## Deployment Topology

```
┌─────────────────────────────────────┐
│         Browser (Client)             │
└────────────┬────────────────────────┘
             │ HTTP/CORS
┌────────────▼────────────────────────┐
│    Node.js API Server                │
│  (Port 3000 by default)              │
│  - Handles CORS                      │
│  - Manages file uploads              │
│  - Spawns Python processors          │
└────────────┬────────────────────────┘
             │ Filesystem I/O
        ┌────▼─────┬────────────┐
        │           │            │
     ┌──▼──┐   ┌───▼───┐  ┌────▼──┐
     │Files│   │Python │  │ SQLite│
     │/    │   │Process│  │  DB   │
     │Upload│   │Engine │  │       │
     └─────┘   └───────┘  └───────┘
```

---

## Scaling Considerations

**Current**: Synchronous processing per request  
**For Scale**:
- Add task queue (Redis/Bull) for long-running extractions
- Implement webhook callbacks for async results
- Containerize Python processor for parallel job workers
- Add database connection pooling and use of enterprise-grade database system
- Consider cloud storage (S3/ Azure Blob Storage) for uploaded files instead of local filesystem

---

## Environment Configuration

**API** (`.env`):
- `PORT`: Express server port (default: 3000)
- `PYTHON_PATH`: Python executable path
- `UPLOAD_DIR`: Upload directory (default: `./uploads`)
- `MAX_UPLOAD_BYTES`: Max file size (default: 10MB)

**Processor**: Configuration via command-line args (`run.py`)

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Server health check |
| `POST` | `/timetable/upload` | Upload timetable file for processing |
| `GET` | `/timetable/:id` | Retrieve extracted activities |
