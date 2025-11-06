# Timetable UI

React application for uploading and processing timetable files.

### Configuration

The API URL is configured via environment variables. The default is `http://localhost:3000`.

To customize, edit `.env`:

```
VITE_API_URL=http://localhost:3000
```

### Development

Start the development server:

```bash
npm run dev
```

The app will be available at `http://localhost:5173`

## Features

- Upload timetable files (.JPG, .JPEG, .PNG, .PDF, .DOCX)
- Process files through the backend API
- Display extracted timetable activities
- View processing results including day, time, and notes

## Usage

1. Click "Choose File" to select a timetable file
2. Click "Upload and Process" to send the file to the API
3. Wait for processing to complete
4. View the extracted activities in the results table
