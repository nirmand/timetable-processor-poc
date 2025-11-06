import { useState } from 'react'
import './App.css'
import CalendarView from './components/CalendarView'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000'

interface TimetableResponse {
  timetable_source_id: number
  file_path: string
  processed_at: string
  activities: Array<{
    id: number
    day: string
    start_time: string
    activity_name: string
    end_time: string
    notes: string | null
  }>
}

function App() {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [response, setResponse] = useState<TimetableResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
      if (validTypes.includes(selectedFile.type)) {
        setFile(selectedFile)
        setError(null)
      } else {
        setFile(null)
        setError('Invalid file type. Please select .JPG, .JPEG, .PNG, .PDF, or .DOCX file.')
      }
    }
  }

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file first.')
      return
    }

    setUploading(true)
    setError(null)
    setResponse(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(`${API_URL}/timetable/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.error || 'Upload failed')
      }

      const data = await res.json()
      // Normalize activity field names: support both 'activity_name' (DB) and
      // legacy 'activity' (processor JSON) so the UI always has activity_name.
      if (data && Array.isArray(data.activities)) {
        console.log(data.activities);
        data.activities = data.activities.map((a: any) => ({
          id: a.id,
          day: a.day,
          start_time: a.start_time,
          end_time: a.end_time,
          notes: a.notes ?? null,
          // prefer activity_name from DB, fallback to processor 'activity' key,
          // then fallback to empty string to avoid rendering null/undefined
          activity_name: a.activity_name ?? a.activity ?? ''
        }))
      }
      setResponse(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred during upload')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="container">
      <h1>Timetable Processor</h1>
      
      <div className="upload-section">
        <label htmlFor="file-input" className="file-label">
          Upload Timetable
        </label>
        <input
          id="file-input"
          type="file"
          accept=".jpg,.jpeg,.png,.pdf,.docx"
          onChange={handleFileChange}
          disabled={uploading}
        />
        
        {file && (
          <p className="file-info">Selected: {file.name}</p>
        )}
        
        <button 
          onClick={handleUpload} 
          disabled={!file || uploading}
          className="upload-button"
        >
          {uploading ? 'Processing...' : 'Upload and Process'}
        </button>
      </div>

      {error && (
        <div className="error-box">
          <strong>Error:</strong> {error}
        </div>
      )}

      {response && (
        <div className="response-box">
          <h2>Processing Results</h2>
          <div className="result-info">
            <p><strong>Timetable Source ID:</strong> {response.timetable_source_id}</p>
            <p><strong>File Path:</strong> {response.file_path}</p>
            <p><strong>Processed At:</strong> {new Date(response.processed_at).toLocaleString()}</p>
          </div>
          
          {response.activities && response.activities.length > 0 && (
            <div className="activities-section">
              <h3>Timetable ({response.activities.length} activities)</h3>
              <CalendarView activities={response.activities} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App
