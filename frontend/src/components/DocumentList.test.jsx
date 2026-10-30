import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import DocumentList from './DocumentList';

describe('DocumentList', () => {
  let mockFetch;
  let abortSpy;

  beforeEach(() => {
    abortSpy = vi.fn();
    global.AbortController = vi.fn(() => ({
      abort: abortSpy,
      signal: 'mock-signal',
    }));

    mockFetch = vi.fn();
    global.fetch = mockFetch;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders document list heading', () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], total: 0 }),
    });

    render(<DocumentList />);
    expect(screen.getByText('Documents')).toBeTruthy();
  });

  it('fetches documents on mount', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [
          { id: 1, filename: 'policy.pdf', created_at: '2024-01-01T00:00:00' },
        ],
        total: 1,
      }),
    });

    render(<DocumentList />);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/documents?limit=10&offset=0',
        expect.any(Object)
      );
    });

    await waitFor(() => {
      expect(screen.getByText('policy.pdf')).toBeTruthy();
    });
  });

  it('displays loading state', () => {
    mockFetch.mockImplementationOnce(
      () =>
        new Promise((resolve) =>
          setTimeout(() => {
            resolve({
              ok: true,
              json: async () => ({ items: [], total: 0 }),
            });
          }, 100)
        )
    );

    render(<DocumentList />);
    expect(screen.getByText('Loading documents...')).toBeTruthy();
  });

  it('displays empty message when no documents', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], total: 0 }),
    });

    render(<DocumentList />);

    await waitFor(() => {
      expect(screen.getByText(/No documents yet/)).toBeTruthy();
    });
  });

  it('displays error message on fetch failure', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    });

    render(<DocumentList />);

    await waitFor(() => {
      expect(screen.getByText(/HTTP 500/)).toBeTruthy();
    });
  });

  it('displays error when fetch throws', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    render(<DocumentList />);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeTruthy();
    });
  });

  it('does not display error on abort', async () => {
    mockFetch.mockRejectedValueOnce(
      Object.assign(new Error('Aborted'), { name: 'AbortError' })
    );

    render(<DocumentList />);

    await waitFor(() => {
      expect(screen.queryByRole('alert')).toBeFalsy();
    });
  });

  it('cleans up fetch on unmount', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], total: 0 }),
    });

    const { unmount } = render(<DocumentList />);

    unmount();

    await waitFor(() => {
      expect(abortSpy).toHaveBeenCalled();
    });
  });

  it('handles pagination - next page', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: Array.from({ length: 10 }, (_, i) => ({
            id: i,
            filename: `doc${i}.pdf`,
            created_at: '2024-01-01T00:00:00',
          })),
          total: 25,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: Array.from({ length: 10 }, (_, i) => ({
            id: i + 10,
            filename: `doc${i + 10}.pdf`,
            created_at: '2024-01-01T00:00:00',
          })),
          total: 25,
        }),
      });

    render(<DocumentList />);

    await waitFor(() => {
      expect(screen.getByText('doc0.pdf')).toBeTruthy();
    });

    const nextButton = screen.getByRole('button', { name: 'Next' });
    fireEvent.click(nextButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/documents?limit=10&offset=10',
        expect.any(Object)
      );
    });

    await waitFor(() => {
      expect(screen.getByText('doc10.pdf')).toBeTruthy();
    });
  });

  it('handles pagination - previous page', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: Array.from({ length: 10 }, (_, i) => ({
            id: i + 10,
            filename: `doc${i + 10}.pdf`,
            created_at: '2024-01-01T00:00:00',
          })),
          total: 25,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: Array.from({ length: 10 }, (_, i) => ({
            id: i,
            filename: `doc${i}.pdf`,
            created_at: '2024-01-01T00:00:00',
          })),
          total: 25,
        }),
      });

    const { rerender } = render(<DocumentList />);

    await waitFor(() => {
      expect(screen.getByText('doc10.pdf')).toBeTruthy();
    });

    // Simulate being on page 1
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: Array.from({ length: 10 }, (_, i) => ({
            id: i + 10,
            filename: `doc${i + 10}.pdf`,
            created_at: '2024-01-01T00:00:00',
          })),
          total: 25,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: Array.from({ length: 10 }, (_, i) => ({
            id: i,
            filename: `doc${i}.pdf`,
            created_at: '2024-01-01T00:00:00',
          })),
          total: 25,
        }),
      });

    rerender(<DocumentList />);

    await waitFor(() => {
      const nextButton = screen.getByRole('button', { name: 'Next' });
      expect(nextButton).not.toHaveAttribute('disabled');
      fireEvent.click(nextButton);
    });

    await waitFor(() => {
      const prevButton = screen.getByRole('button', { name: 'Previous' });
      expect(prevButton).not.toHaveAttribute('disabled');
      fireEvent.click(prevButton);
    });

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/documents?limit=10&offset=0',
        expect.any(Object)
      );
    });
  });

  it('disables navigation buttons at boundaries', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: Array.from({ length: 5 }, (_, i) => ({
          id: i,
          filename: `doc${i}.pdf`,
          created_at: '2024-01-01T00:00:00',
        })),
        total: 5,
      }),
    });

    render(<DocumentList />);

    await waitFor(() => {
      const prevButton = screen.getByRole('button', { name: 'Previous' });
      const nextButton = screen.getByRole('button', { name: 'Next' });
      expect(prevButton).toHaveAttribute('disabled');
      expect(nextButton).toHaveAttribute('disabled');
    });
  });

  it('calls onSelectDocument when View button clicked', async () => {
    const onSelectDocument = vi.fn();

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [
          { id: 1, filename: 'policy.pdf', created_at: '2024-01-01T00:00:00' },
        ],
        total: 1,
      }),
    });

    render(<DocumentList onSelectDocument={onSelectDocument} />);

    await waitFor(() => {
      expect(screen.getByText('policy.pdf')).toBeTruthy();
    });

    const viewButton = screen.getByRole('button', { name: 'View' });
    fireEvent.click(viewButton);

    expect(onSelectDocument).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 1,
        filename: 'policy.pdf',
      })
    );
  });

  it('handles delete with confirmation', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: [
            { id: 1, filename: 'policy.pdf', created_at: '2024-01-01T00:00:00' },
          ],
          total: 1,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: [], total: 0 }),
      });

    window.confirm = vi.fn(() => true);

    render(<DocumentList />);

    await waitFor(() => {
      expect(screen.getByText('policy.pdf')).toBeTruthy();
    });

    const deleteButton = screen.getByRole('button', { name: 'Delete' });
    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/documents/1',
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  it('handles delete cancellation', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [
          { id: 1, filename: 'policy.pdf', created_at: '2024-01-01T00:00:00' },
        ],
        total: 1,
      }),
    });

    window.confirm = vi.fn(() => false);

    render(<DocumentList />);

    await waitFor(() => {
      expect(screen.getByText('policy.pdf')).toBeTruthy();
    });

    const deleteButton = screen.getByRole('button', { name: 'Delete' });
    fireEvent.click(deleteButton);

    // Should not call DELETE endpoint
    expect(mockFetch).toHaveBeenCalledTimes(1); // Only initial fetch
  });

  it('handles delete error', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: [
            { id: 1, filename: 'policy.pdf', created_at: '2024-01-01T00:00:00' },
          ],
          total: 1,
        }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      });

    window.confirm = vi.fn(() => true);

    render(<DocumentList />);

    await waitFor(() => {
      expect(screen.getByText('policy.pdf')).toBeTruthy();
    });

    const deleteButton = screen.getByRole('button', { name: 'Delete' });
    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(screen.getByText(/Failed to delete document/)).toBeTruthy();
    });
  });

  it('no infinite loop on dependency change', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], total: 0 }),
    });

    const { rerender } = render(<DocumentList />);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    rerender(<DocumentList />);

    // Should still be 1 (no additional fetch)
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });
});
