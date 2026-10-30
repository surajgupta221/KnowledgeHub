import { useState, useEffect, useRef, useCallback } from 'react';

export default function DocumentList({ onSelectDocument }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentPage, setCurrentPage] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const abortControllerRef = useRef(null);

  const ITEMS_PER_PAGE = 10;

  const fetchDocuments = useCallback(async (page) => {
    setLoading(true);
    setError(null);

    // Cancel previous request if still in-flight
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();

    try {
      const offset = page * ITEMS_PER_PAGE;
      const response = await fetch(`/api/documents?limit=${ITEMS_PER_PAGE}&offset=${offset}`, {
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setDocuments(data.items || []);
      setTotalCount(data.total || 0);
    } catch (err) {
      // Abort errors are expected on unmount, don't show them
      if (err.name !== 'AbortError') {
        setError(err.message || 'Failed to load documents');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch documents on page change
  useEffect(() => {
    fetchDocuments(currentPage);
  }, [currentPage, fetchDocuments]);

  // Cleanup: abort fetch on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const handlePreviousPage = () => {
    if (currentPage > 0) {
      setCurrentPage(currentPage - 1);
    }
  };

  const handleNextPage = () => {
    const totalPages = Math.ceil(totalCount / ITEMS_PER_PAGE);
    if (currentPage < totalPages - 1) {
      setCurrentPage(currentPage + 1);
    }
  };

  const handleDelete = async (docId) => {
    if (!confirm('Delete this document?')) return;

    try {
      const response = await fetch(`/api/documents/${docId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // Refresh list
      await fetchDocuments(currentPage);
    } catch (err) {
      setError(`Failed to delete document: ${err.message}`);
    }
  };

  const totalPages = Math.ceil(totalCount / ITEMS_PER_PAGE);
  const hasNextPage = currentPage < totalPages - 1;
  const hasPreviousPage = currentPage > 0;

  return (
    <div className="document-list">
      <h2>Documents</h2>

      {error && (
        <div className="error-message" role="alert">
          {error}
        </div>
      )}

      {loading && <div className="loading">Loading documents...</div>}

      {!loading && documents.length === 0 && (
        <div className="empty-message">No documents yet. Upload one to get started.</div>
      )}

      {!loading && documents.length > 0 && (
        <div>
          <ul className="document-items">
            {documents.map((doc) => (
              <li key={doc.id} className="document-item">
                <div className="document-header">
                  <h3>{doc.filename}</h3>
                  <div className="document-meta">
                    Uploaded: {new Date(doc.created_at).toLocaleDateString()}
                  </div>
                </div>
                <div className="document-actions">
                  <button
                    className="btn-select"
                    onClick={() => onSelectDocument && onSelectDocument(doc)}
                  >
                    View
                  </button>
                  <button className="btn-delete" onClick={() => handleDelete(doc.id)}>
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>

          {totalPages > 1 && (
            <div className="pagination">
              <button
                disabled={!hasPreviousPage}
                onClick={handlePreviousPage}
                className="btn-pagination"
              >
                Previous
              </button>
              <span className="page-info">
                Page {currentPage + 1} of {totalPages}
              </span>
              <button
                disabled={!hasNextPage}
                onClick={handleNextPage}
                className="btn-pagination"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
