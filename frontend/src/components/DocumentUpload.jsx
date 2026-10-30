import { useState, useRef } from 'react';

/**
 * DocumentUpload component for uploading policy documents.
 *
 * Features:
 * - File input validation (PDF/text only, max 10MB)
 * - FormData for multipart/form-data submission
 * - Progress tracking via XMLHttpRequest
 * - Error handling and user feedback
 * - Clears form on successful upload
 */
export default function DocumentUpload({ onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const fileInputRef = useRef(null);

  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
  const ALLOWED_TYPES = ['application/pdf', 'text/plain', 'text/csv'];

  const handleFileChange = (e) => {
    const selectedFile = e.target.files?.[0];
    setError(null);
    setSuccess(false);

    if (!selectedFile) {
      setFile(null);
      return;
    }

    // Validate file type
    if (!ALLOWED_TYPES.includes(selectedFile.type)) {
      setError('Invalid file type. Please upload a PDF, text, or CSV file.');
      setFile(null);
      return;
    }

    // Validate file size
    if (selectedFile.size > MAX_FILE_SIZE) {
      setError('File too large. Maximum size is 10MB.');
      setFile(null);
      return;
    }

    setFile(selectedFile);
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file first.');
      return;
    }

    setUploading(true);
    setProgress(0);
    setError(null);
    setSuccess(false);

    // Use XMLHttpRequest for progress tracking
    const xhr = new XMLHttpRequest();

    // Track upload progress
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const percentComplete = (e.loaded / e.total) * 100;
        setProgress(Math.round(percentComplete));
      }
    });

    // Handle completion
    xhr.addEventListener('load', () => {
      setUploading(false);

      if (xhr.status === 200 || xhr.status === 201) {
        setSuccess(true);
        setFile(null);
        setProgress(0);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        if (onUploadSuccess) {
          onUploadSuccess();
        }
      } else {
        let errorMsg = 'Upload failed';
        try {
          const response = JSON.parse(xhr.responseText);
          errorMsg = response.detail || response.error || errorMsg;
        } catch (e) {
          errorMsg = `Upload failed: ${xhr.statusText}`;
        }
        setError(errorMsg);
      }
    });

    // Handle error
    xhr.addEventListener('error', () => {
      setUploading(false);
      setError('Network error during upload.');
    });

    // Handle abort
    xhr.addEventListener('abort', () => {
      setUploading(false);
      setError('Upload cancelled.');
    });

    // Prepare FormData
    const formData = new FormData();
    formData.append('file', file);

    // Send request
    xhr.open('POST', 'http://localhost:8000/api/documents', true);
    xhr.send(formData);
  };

  const handleClear = () => {
    setFile(null);
    setProgress(0);
    setError(null);
    setSuccess(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="document-upload">
      <h3>Upload Document</h3>

      {error && (
        <div className="error-message" role="alert">
          {error}
        </div>
      )}

      {success && (
        <div className="success-message" role="status">
          Document uploaded successfully!
        </div>
      )}

      <div className="file-input-wrapper">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.csv"
          onChange={handleFileChange}
          disabled={uploading}
          className="file-input"
          aria-label="Select document file"
        />
        {file && (
          <div className="file-name">
            Selected: {file.name} ({(file.size / 1024 / 1024).toFixed(2)}MB)
          </div>
        )}
      </div>

      {uploading && (
        <div className="progress-container">
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${progress}%` }}
              role="progressbar"
              aria-valuenow={progress}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
          <div className="progress-text">{progress}%</div>
        </div>
      )}

      <div className="button-group">
        <button
          className="btn-upload"
          onClick={handleUpload}
          disabled={!file || uploading}
        >
          {uploading ? 'Uploading...' : 'Upload'}
        </button>
        <button
          className="btn-clear"
          onClick={handleClear}
          disabled={!file || uploading}
        >
          Clear
        </button>
      </div>

      <div className="upload-info">
        <p>Supported: PDF, TXT, CSV</p>
        <p>Max size: 10MB</p>
      </div>
    </div>
  );
}
