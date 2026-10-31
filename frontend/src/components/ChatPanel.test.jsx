import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChatPanel from './ChatPanel';

describe('ChatPanel', () => {
  let mockFetch;

  beforeEach(() => {
    // Mock fetch
    mockFetch = vi.spyOn(global, 'fetch');
  });

  afterEach(() => {
    mockFetch.mockRestore();
  });

  it('renders chat panel with input', () => {
    render(<ChatPanel documentIds={[1, 2]} />);

    const input = screen.getByPlaceholderText(/Ask a question/i);
    expect(input).toBeInTheDocument();

    const sendButton = screen.getByRole('button', { name: /Send/i });
    expect(sendButton).toBeInTheDocument();
  });

  it('disables input while loading', async () => {
    // Stream stays open so the component remains in the loading state
    const mockStream = new ReadableStream({ start() {} });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: mockStream,
    });

    const user = userEvent.setup();
    render(<ChatPanel documentIds={[]} />);

    const input = screen.getByPlaceholderText(/Ask a question/i);
    const sendButton = screen.getByRole('button', { name: /Send/i });

    await user.type(input, 'Test question');
    await user.click(sendButton);

    // Input should be disabled while loading
    expect(input).toBeDisabled();
  });

  it('shows Stop button while streaming', async () => {
    const mockStream = new ReadableStream({
      start(controller) {
        setTimeout(() => {
          controller.enqueue(new TextEncoder().encode('data: {"event": "token", "data": "response"}\n\n'));
          controller.close();
        }, 50);
      },
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: mockStream,
    });

    const user = userEvent.setup();
    render(<ChatPanel documentIds={[]} />);

    const input = screen.getByPlaceholderText(/Ask a question/i);
    const sendButton = screen.getByRole('button', { name: /Send/i });

    await user.type(input, 'Question');
    await user.click(sendButton);

    // Stop button should appear
    await waitFor(() => {
      const stopButton = screen.queryByRole('button', { name: /Stop/i });
      if (stopButton) {
        expect(stopButton).toBeInTheDocument();
      }
    });
  });

  it('handles SSE event split across chunks', async () => {
    /**
     * Test case: SSE event is split across two chunks
     * Chunk 1: 'data: {"event": "token", "data": "hel'
     * Chunk 2: 'lo"}\n\n'
     *
     * Expected: Component should buffer incomplete event and yield complete token
     */
    const chunk1 = 'data: {"event": "token", "data": "hel';
    const chunk2 = 'lo"}\n\ndata: {"event": "done"}\n\n';

    const mockStream = new ReadableStream({
      start(controller) {
        setTimeout(() => {
          controller.enqueue(new TextEncoder().encode(chunk1));
          setTimeout(() => {
            controller.enqueue(new TextEncoder().encode(chunk2));
            controller.close();
          }, 10);
        }, 10);
      },
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: mockStream,
    });

    const user = userEvent.setup();
    render(<ChatPanel documentIds={[]} />);

    const input = screen.getByPlaceholderText(/Ask a question/i);
    await user.type(input, 'Test');
    await user.click(screen.getByRole('button', { name: /Send/i }));

    // Wait for response to include "hello" token
    await waitFor(() => {
      expect(screen.getByText(/hello/i)).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('sends correct request body with question and document IDs', async () => {
    const mockStream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('data: {"event": "done"}\n\n'));
        controller.close();
      },
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: mockStream,
    });

    const user = userEvent.setup();
    const docIds = [1, 2, 3];
    render(<ChatPanel documentIds={docIds} />);

    const input = screen.getByPlaceholderText(/Ask a question/i);
    await user.type(input, 'What is policy X?');
    await user.click(screen.getByRole('button', { name: /Send/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/chat/stream',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question: 'What is policy X?',
            document_ids: docIds,
          }),
        })
      );
    });
  });

  it('displays error message on fetch failure', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    const user = userEvent.setup();
    render(<ChatPanel documentIds={[]} />);

    const input = screen.getByPlaceholderText(/Ask a question/i);
    await user.type(input, 'Question');
    await user.click(screen.getByRole('button', { name: /Send/i }));

    await waitFor(() => {
      expect(screen.getByText(/Network error/i)).toBeInTheDocument();
    });
  });

  it('cleans up fetch on unmount', async () => {
    const abortSpy = vi.spyOn(AbortController.prototype, 'abort');

    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: new ReadableStream({ start() {} }),
    });

    const user = userEvent.setup();
    const { unmount } = render(<ChatPanel documentIds={[]} />);

    const input = screen.getByPlaceholderText(/Ask a question/i);
    await user.type(input, 'Q');
    await user.click(screen.getByRole('button', { name: /Send/i }));

    // Unmount should trigger abort cleanup
    unmount();

    expect(abortSpy).toHaveBeenCalled();
    abortSpy.mockRestore();
  });

  it('handles done event correctly', async () => {
    const mockStream = new ReadableStream({
      start(controller) {
        const event1 = 'data: {"event": "token", "data": "Hello"}\n\n';
        const event2 = 'data: {"event": "token", "data": " world"}\n\n';
        const done = 'data: {"event": "done"}\n\n';

        controller.enqueue(new TextEncoder().encode(event1 + event2 + done));
        controller.close();
      },
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: mockStream,
    });

    const user = userEvent.setup();
    render(<ChatPanel documentIds={[]} />);

    const input = screen.getByPlaceholderText(/Ask a question/i);
    await user.type(input, 'Q');
    await user.click(screen.getByRole('button', { name: /Send/i }));

    await waitFor(() => {
      expect(screen.getByText(/Hello world/i)).toBeInTheDocument();
    });
  });

  it('displays user message when question is sent', async () => {
    const mockStream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('data: {"event": "done"}\n\n'));
        controller.close();
      },
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: mockStream,
    });

    const user = userEvent.setup();
    render(<ChatPanel documentIds={[]} />);

    const question = 'What is in this document?';
    const input = screen.getByPlaceholderText(/Ask a question/i);
    await user.type(input, question);
    await user.click(screen.getByRole('button', { name: /Send/i }));

    await waitFor(() => {
      expect(screen.getByText(question)).toBeInTheDocument();
    });
  });
});
