import { useState, useRef } from 'react';
import Login from './components/Login';
import DocumentList from './components/DocumentList';
import ChatPanel from './components/ChatPanel';
import DocumentUpload from './components/DocumentUpload';
import './App.css';

export default function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [selectedDocuments, setSelectedDocuments] = useState([]);
  const documentListRef = useRef(null);

  const handleLogin = (userId) => {
    setCurrentUser(userId);
    // Clear selections when switching users
    setSelectedDocuments([]);
  };

  const handleSelectDocument = (doc) => {
    setSelectedDocuments((prev) => {
      const exists = prev.some((d) => d.id === doc.id);
      if (exists) {
        return prev.filter((d) => d.id !== doc.id);
      }
      return [...prev, doc];
    });
  };

  const handleUploadSuccess = () => {
    // Refresh document list after successful upload
    if (documentListRef.current) {
      documentListRef.current.refresh?.();
    }
  };

  if (!currentUser) {
    return <Login onLoginSuccess={handleLogin} />;
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1>KnowledgeHub</h1>
          <p>Policy document assistant with streaming QA</p>
        </div>
        <div className="header-right">
          <span className="user-badge">👤 {currentUser}</span>
          <button
            className="btn-logout-header"
            onClick={() => {
              sessionStorage.removeItem('current_user');
              setCurrentUser(null);
              setSelectedDocuments([]);
            }}
          >
            Logout
          </button>
        </div>
      </header>

      <div className="app-container">
        <aside className="sidebar">
          <DocumentUpload 
            currentUser={currentUser}
            onUploadSuccess={handleUploadSuccess} 
          />

          <DocumentList
            ref={documentListRef}
            currentUser={currentUser}
            onSelectDocument={handleSelectDocument}
          />

          {selectedDocuments.length > 0 && (
            <div className="selected-documents">
              <h3>Selected ({selectedDocuments.length})</h3>
              <ul>
                {selectedDocuments.map((doc) => (
                  <li key={doc.id} className="selected-item">
                    {doc.filename}
                    <button
                      className="btn-deselect"
                      onClick={() => handleSelectDocument(doc)}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>

        <main className="main-content">
          <ChatPanel
            currentUser={currentUser}
            documentIds={selectedDocuments.map((d) => d.id)}
          />
        </main>
      </div>
    </div>
  );
}
