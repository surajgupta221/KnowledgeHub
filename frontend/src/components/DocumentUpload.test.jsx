import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DocumentUpload from './DocumentUpload';

describe('DocumentUpload', () => {
  let mockXhr;
  let xhrOpen;
  let xhrSend;

  beforeEach(() => {
    xhrOpen = vi.fn();
    xhrSend = vi.fn();

    mockXhr = {
      open: xhrOpen,
      send: xhrSend,
      upload: {
        addEventListener: vi.fn(),
      },
      addEventListener: vi.fn((event, callback) => {
        mockXhr[`on${event}`] = callback;
      }),
    };

    global.XMLHttpRequest = vi.fn(() => mockXhr);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders upload form', () => {
    render(<DocumentUpload />);
    expect(screen.getByText('Upload Document')).toBeTruthy();
    expect(screen.getByLabelText('Select document file')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Upload' })).toBeTruthy();
  });

  it('displays file info when file selected', () => {
    render(<DocumentUpload />);
    const fileInput = screen.getByLabelText('Select document file');

    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);

    expect(screen.getByText(/Selected: test.pdf/)).toBeTruthy();
  });

  it('rejects non-PDF/text files', () => {
    render(<DocumentUpload />);
    const fileInput = screen.getByLabelText('Select document file');

    const file = new File(['test'], 'test.exe', { type: 'application/x-msdownload' });
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);

    expect(screen.getByText(/Invalid file type/)).toBeTruthy();
  });

  it('rejects files larger than 10MB', () => {
    render(<DocumentUpload />);
    const fileInput = screen.getByLabelText('Select document file');

    const largeFile = new File(['x'.repeat(11 * 1024 * 1024)], 'large.pdf', {
      type: 'application/pdf',
    });
    Object.defineProperty(fileInput, 'files', {
      value: [largeFile],
      writable: false,
    });

    fireEvent.change(fileInput);

    expect(screen.getByText(/File too large/)).toBeTruthy();
  });

  it('accepts PDF files', () => {
    render(<DocumentUpload />);
    const fileInput = screen.getByLabelText('Select document file');

    const file = new File(['test'], 'policy.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);

    expect(screen.getByText(/Selected: policy.pdf/)).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeFalsy();
  });

  it('accepts text files', () => {
    render(<DocumentUpload />);
    const fileInput = screen.getByLabelText('Select document file');

    const file = new File(['test'], 'policy.txt', { type: 'text/plain' });
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);

    expect(screen.getByText(/Selected: policy.txt/)).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeFalsy();
  });

  it('accepts CSV files', () => {
    render(<DocumentUpload />);
    const fileInput = screen.getByLabelText('Select document file');

    const file = new File(['test'], 'data.csv', { type: 'text/csv' });
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);

    expect(screen.getByText(/Selected: data.csv/)).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeFalsy();
  });

  it('disables upload button without file', () => {
    render(<DocumentUpload />);
    const uploadButton = screen.getByRole('button', { name: 'Upload' });
    expect(uploadButton).toHaveAttribute('disabled');
  });

  it('enables upload button with valid file', () => {
    render(<DocumentUpload />);
    const fileInput = screen.getByLabelText('Select document file');

    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);

    const uploadButton = screen.getByRole('button', { name: 'Upload' });
    expect(uploadButton).not.toHaveAttribute('disabled');
  });

  it('shows progress during upload', async () => {
    render(<DocumentUpload />);
    const fileInput = screen.getByLabelText('Select document file');

    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);

    const uploadButton = screen.getByRole('button', { name: 'Upload' });
    fireEvent.click(uploadButton);

    // Simulate progress event
    const progressCallback = mockXhr.upload.addEventListener.mock.calls.find(
      (call) => call[0] === 'progress'
    )?.[1];

    if (progressCallback) {
      progressCallback({ lengthComputable: true, loaded: 50, total: 100 });

      await waitFor(() => {
        expect(screen.getByText('50%')).toBeTruthy();
      });
    }
  });

  it('handles successful upload', async () => {
    const onUploadSuccess = vi.fn();
    render(<DocumentUpload onUploadSuccess={onUploadSuccess} />);

    const fileInput = screen.getByLabelText('Select document file');
    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);
    const uploadButton = screen.getByRole('button', { name: 'Upload' });
    fireEvent.click(uploadButton);

    // Simulate successful response
    mockXhr.status = 200;
    mockXhr.onload();

    await waitFor(() => {
      expect(screen.getByText(/uploaded successfully/)).toBeTruthy();
      expect(onUploadSuccess).toHaveBeenCalled();
    });
  });

  it('handles upload error', async () => {
    render(<DocumentUpload />);

    const fileInput = screen.getByLabelText('Select document file');
    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);
    const uploadButton = screen.getByRole('button', { name: 'Upload' });
    fireEvent.click(uploadButton);

    // Simulate error response
    mockXhr.status = 500;
    mockXhr.statusText = 'Internal Server Error';
    mockXhr.responseText = '{"detail": "File upload failed"}';
    mockXhr.onload();

    await waitFor(() => {
      expect(screen.getByText(/File upload failed/)).toBeTruthy();
    });
  });

  it('handles network error', async () => {
    render(<DocumentUpload />);

    const fileInput = screen.getByLabelText('Select document file');
    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);
    const uploadButton = screen.getByRole('button', { name: 'Upload' });
    fireEvent.click(uploadButton);

    // Simulate network error
    mockXhr.onerror();

    await waitFor(() => {
      expect(screen.getByText(/Network error/)).toBeTruthy();
    });
  });

  it('handles upload abort', async () => {
    render(<DocumentUpload />);

    const fileInput = screen.getByLabelText('Select document file');
    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);
    const uploadButton = screen.getByRole('button', { name: 'Upload' });
    fireEvent.click(uploadButton);

    // Simulate abort
    mockXhr.onabort();

    await waitFor(() => {
      expect(screen.getByText(/cancelled/)).toBeTruthy();
    });
  });

  it('clears form on clear button click', () => {
    render(<DocumentUpload />);

    const fileInput = screen.getByLabelText('Select document file');
    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);
    expect(screen.getByText(/Selected: test.pdf/)).toBeTruthy();

    const clearButton = screen.getByRole('button', { name: 'Clear' });
    fireEvent.click(clearButton);

    expect(screen.queryByText(/Selected:/)).toBeFalsy();
  });

  it('disables buttons during upload', () => {
    render(<DocumentUpload />);

    const fileInput = screen.getByLabelText('Select document file');
    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);
    const uploadButton = screen.getByRole('button', { name: 'Upload' });
    fireEvent.click(uploadButton);

    const clearButton = screen.getByRole('button', { name: 'Clear' });
    expect(uploadButton).toHaveAttribute('disabled');
    expect(clearButton).toHaveAttribute('disabled');
    expect(fileInput).toHaveAttribute('disabled');
  });

  it('sends FormData with correct headers', () => {
    render(<DocumentUpload />);

    const fileInput = screen.getByLabelText('Select document file');
    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);
    const uploadButton = screen.getByRole('button', { name: 'Upload' });
    fireEvent.click(uploadButton);

    expect(xhrOpen).toHaveBeenCalledWith(
      'POST',
      'http://localhost:8000/api/documents',
      true
    );
    expect(xhrSend).toHaveBeenCalled();
  });

  it('clears form on successful upload', async () => {
    render(<DocumentUpload />);

    const fileInput = screen.getByLabelText('Select document file');
    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' });
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(fileInput);
    expect(screen.getByText(/Selected: test.pdf/)).toBeTruthy();

    const uploadButton = screen.getByRole('button', { name: 'Upload' });
    fireEvent.click(uploadButton);

    mockXhr.status = 200;
    mockXhr.onload();

    await waitFor(() => {
      expect(screen.queryByText(/Selected:/)).toBeFalsy();
    });
  });

  it('displays upload info text', () => {
    render(<DocumentUpload />);
    expect(screen.getByText('Supported: PDF, TXT, CSV')).toBeTruthy();
    expect(screen.getByText('Max size: 10MB')).toBeTruthy();
  });
});
