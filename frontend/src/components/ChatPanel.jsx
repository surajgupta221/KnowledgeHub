import React, { useState, useEffect, useRef, useCallback } from 'react';

/**
 * ChatPanel component with streaming SSE support.
 *
 * Features:
 * - Streams tokens from backend via Server-Sent Events (SSE)
 * - Handles split SSE events across chunks (buffers incomplete lines)
 * - AbortController for Stop button
 * - Loading/error/stopped states
 * - Input disabled while streaming
 * - Cleanup on unmount
 */
export default function ChatPanel({ currentUser, documentIds = [] }) {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [stopped, setStopped] = useState(false);

  const abortControllerRef = useRef(null);
  const bufferRef = useRef('');
  const messageIdRef = useRef(0);

  /**
   * Parse SSE event from buffered lines.
   *
   * SSE format: "data: {...}\n\n"
   * Events may be split across chunks, so we buffer and look for "\n\n" delimiter.
   *
   * Returns: { event, data } or null if incomplete
   */
  const parseSSEEvent = (line) => {
    if (!line.startsWith('data:')) return null;
    try {
      const dataStr = line.slice(5).trim();
      const parsed = JSON.parse(dataStr);
      return parsed;
    } catch (e) {
      console.error('Failed to parse SSE event:', e);
      return null;
    }
  };

  /**
   * Handle streaming response from backend.
   *
   * Reads response body as a stream, decodes chunks with TextDecoder,
   * buffers incomplete SSE events, and yields complete events.
   *
   * On client disconnect (AbortController abort), fetch is cancelled
   * and resources cleaned up.
   */
  const handleStream = useCallback(async (questionText, assistantId) => {
    setLoading(true);
    setStopped(false);
    setError(null);
    bufferRef.current = '';

    abortControllerRef.current = new AbortController();

    // Tokens are accumulated here and written to the assistant message by id
    let content = '';
    const showContent = () =>
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, content } : m))
      );

    try {
      const response = await fetch('http://localhost:8000/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': currentUser,
        },
        body: JSON.stringify({
          question: questionText,
          document_ids: documentIds,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`Chat error: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let finished = false;

      while (!finished) {
        const { done, value } = await reader.read();
        if (done) break;

        bufferRef.current += decoder.decode(value, { stream: true });

        // Split on "\n\n" to find complete SSE events; keep the incomplete tail
        const events = bufferRef.current.split('\n\n');
        bufferRef.current = events.pop() || '';

        for (const eventLine of events) {
          if (!eventLine.trim()) continue;

          const eventData = parseSSEEvent(eventLine);
          if (!eventData) continue;

          if (eventData.event === 'token') {
            content += eventData.data || '';
          } else if (eventData.event === 'done') {
            finished = true;
            break;
          } else if (eventData.event === 'error') {
            setError(eventData.data || 'Unknown error');
            finished = true;
            break;
          }
        }

        showContent();
      }

      setLoading(false);
    } catch (err) {
      if (err.name === 'AbortError') {
        setStopped(true);
      } else {
        setError(err.message || 'Failed to fetch chat response');
      }
      setLoading(false);
    }
  }, [currentUser, documentIds]);

  /**
   * Handle Stop button click.
   *
   * Aborts the fetch request, which closes the upstream connection
   * and stops the stream.
   */
  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setStopped(true);
      setLoading(false);
    }
  };

  /**
   * Cleanup on component unmount.
   *
   * Ensures fetch is aborted if component is unmounted while streaming.
   */
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (question.trim() && !loading) {
      const assistantId = messageIdRef.current + 1;
      setMessages((prev) => [
        ...prev,
        { id: messageIdRef.current, role: 'user', content: question },
        { id: assistantId, role: 'assistant', content: '' },
      ]);
      messageIdRef.current += 2;
      handleStream(question, assistantId);
      setQuestion('');
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-messages">
        {messages
          .filter((msg) => msg.role === 'user' || msg.content)
          .map((msg) => (
            <div key={msg.id} className={`message message-${msg.role}`}>
              <strong>{msg.role === 'user' ? 'You' : 'Assistant'}:</strong>
              <p>{msg.content}</p>
            </div>
          ))}
      </div>

      {error && <div className="error-message">{error}</div>}
      {stopped && <div className="stopped-message">Stream stopped by user</div>}

      <form onSubmit={handleSubmit} className="chat-form">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about the documents..."
          disabled={loading}
          rows="3"
        />
        <div className="form-buttons">
          <button type="submit" disabled={loading || !question.trim()}>
            {loading ? 'Streaming...' : 'Send'}
          </button>
          {loading && (
            <button type="button" onClick={handleStop} className="stop-button">
              Stop
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
