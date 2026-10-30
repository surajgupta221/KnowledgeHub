import { useState } from 'react';
import DocumentList from './components/DocumentList';
import ChatPanel from './components/ChatPanel';
import './App.css';

export default function App() {
  const [selectedDocuments, setSelectedDocuments] = useState([]);

  const handleSelectDocument = (doc) => {
    setSelectedDocuments((prev) => {
      const exists = prev.some((d) => d.id === doc.id);
      if (exists) {
        return prev.filter((d) => d.id !== doc.id);
      }
      return [...prev, doc];
    });
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>KnowledgeHub</h1>
        <p>Policy document assistant with streaming QA</p>
      </header>

      <div className="app-container">
        <aside className="sidebar">
          <DocumentList onSelectDocument={handleSelectDocument} />

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
            documentIds={selectedDocuments.map((d) => d.id)}
          />
        </main>
      </div>
    </div>
  );
}
