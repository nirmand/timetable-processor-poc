import { useState } from 'react'
import './App.css'

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
              <h3>Extracted Activities ({response.activities.length})</h3>
              <table className="activities-table">
                <thead>
                  <tr>
                    <th>Day</th>
                    <th>Start Time</th>
                    <th>End Time</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {response.activities.map((activity) => (
                    <tr key={activity.id}>
                      <td>{activity.day}</td>
                      <td>{activity.start_time}</td>
                      <td>{activity.end_time}</td>
                      <td>{activity.notes || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App
