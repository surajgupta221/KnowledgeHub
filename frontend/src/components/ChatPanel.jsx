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
export default function ChatPanel({ documentIds = [] }) {
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
  const handleStream = useCallback(async () => {
    setLoading(true);
    setStopped(false);
    setError(null);
    bufferRef.current = '';

    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch('http://localhost:8000/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question,
          document_ids: documentIds,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`Chat error: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder({ stream: true });

      let currentMessage = {
        id: messageIdRef.current++,
        role: 'assistant',
        content: '',
      };

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          // Stream completed, add final message if it has content
          if (currentMessage.content.trim()) {
            setMessages((prev) => [...prev, currentMessage]);
          }
          break;
        }

        // Decode chunk
        const chunk = decoder.decode(value, { stream: true });
        bufferRef.current += chunk;

        // Split on "\n\n" to find complete SSE events
        const events = bufferRef.current.split('\n\n');

        // Keep the last incomplete event in buffer
        bufferRef.current = events.pop() || '';

        // Process complete events
        for (const eventLine of events) {
          if (!eventLine.trim()) continue;

          const eventData = parseSSEEvent(eventLine);
          if (!eventData) continue;

          if (eventData.event === 'token') {
            currentMessage.content += eventData.data || '';
          } else if (eventData.event === 'done') {
            if (currentMessage.content.trim()) {
              setMessages((prev) => [...prev, currentMessage]);
            }
            currentMessage = {
              id: messageIdRef.current++,
              role: 'assistant',
              content: '',
            };
          } else if (eventData.event === 'error') {
            setError(eventData.data || 'Unknown error');
            break;
          }
        }

        // Update messages state to show streaming progress
        setMessages((prev) => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
            updated[lastIdx] = { ...updated[lastIdx], content: currentMessage.content };
          } else if (currentMessage.content.trim()) {
            updated.push(currentMessage);
          }
          return updated;
        });
      }

      setLoading(false);
    } catch (err) {
      if (err.name === 'AbortError') {
        setStopped(true);
      } else {
        setError(err.message || 'Failed to fetch chat response');
        setLoading(false);
      }
    }
  }, [question, documentIds]);

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
      // Add user message
      setMessages((prev) => [
        ...prev,
        {
          id: messageIdRef.current++,
          role: 'user',
          content: question,
        },
      ]);
      handleStream();
      setQuestion('');
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-messages">
        {messages.map((msg) => (
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
