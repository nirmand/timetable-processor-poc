# Developer Setup Guide

## 1. Timetable UI (Frontend)

A React-based UI for timetable upload and processing.

### Prerequisites
- Node.js (Latest LTS version)
- npm or yarn

### Setup Steps
1. Navigate to the UI directory:
   ```bash
   cd src/timetable-ui
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start development server:
   ```bash
   npm run dev
   ```
The application will be available at `http://localhost:5173`

## 2. Timetable API (Backend)

A Node.js/Express API server for timetable processing.

### Prerequisites
- Node.js (Latest LTS version)
- npm or yarn

### Setup Steps
1. Navigate to the API directory:
   ```bash
   cd src/timetable-api
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Build the TypeScript code:
   ```bash
   npm run build
   ```
4. Start development server:
   ```bash
   npm run start
   ```

## 3. Database Setup

The application uses SQLite for data storage. The database will be automatically created in the `db` directory when needed.

### Prerequisites
- No additional prerequisites - SQLite is embedded and managed by the application

### Database Location
- The database file will be created at: `db/timetable.sqlite`
- The schema includes two tables:
  - `timetable_sources`: Stores metadata about uploaded timetables
  - `extracted_activities`: Stores the extracted timetable entries

### Automatic Setup
The database and its tables are automatically created when:
1. The API server starts up, or
2. The first timetable is processed

No manual database setup is required. Just ensure the `db` directory exists in the project root:

The API will be available at `http://localhost:3000`

## 3. Processor Engine (Python)

A Python-based engine for timetable processing and OCR.

### Prerequisites
- Python 3.12 or higher
- pip (Python package manager)

### Setup Steps
1. Navigate to the processor directory:
   ```bash
   cd src/processor
   ```
2. Create and activate a virtual environment (recommended):
   ```bash
   # On Windows
   python -m venv venv
   .\venv\Scripts\activate

   # On Unix/MacOS
   python -m venv venv
   source venv/bin/activate
   ```
3. Install the package in development mode:
   ```bash
   pip install -e .
   ```

## Development Workflow

1. Start the API server (will be used by the UI)
2. Start the UI development server
Note: Processor engine (Python app) is invoked directly by API when needed and hence not required to run separately.

Each component can be developed independently, but for full functionality, both UI and API app needs to be running.
