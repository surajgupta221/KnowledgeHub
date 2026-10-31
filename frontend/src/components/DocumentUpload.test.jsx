import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DocumentUpload from './DocumentUpload';

function selectFile(file) {
  const fileInput = screen.getByLabelText('Select document file');
  Object.defineProperty(fileInput, 'files', {
    value: [file],
    writable: false,
    configurable: true,
  });
  fireEvent.change(fileInput);
  return fileInput;
}

const txtFile = (name = 'test.txt', body = 'Passwords rotate every 90 days.') =>
  new File([body], name, { type: 'text/plain' });

describe('DocumentUpload', () => {
  let mockXhr;
  let xhrOpen;
  let xhrSend;
  let xhrSetRequestHeader;

  beforeEach(() => {
    xhrOpen = vi.fn();
    xhrSend = vi.fn();
    xhrSetRequestHeader = vi.fn();

    mockXhr = {
      open: xhrOpen,
      send: xhrSend,
      setRequestHeader: xhrSetRequestHeader,
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

  // The file is read asynchronously before the request is sent
  const clickUploadAndWaitForSend = async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Upload' }));
    await waitFor(() => expect(xhrSend).toHaveBeenCalled());
  };

  it('renders upload form', () => {
    render(<DocumentUpload currentUser="user_a" />);
    expect(screen.getByText('Upload Document')).toBeTruthy();
    expect(screen.getByLabelText('Select document file')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Upload' })).toBeTruthy();
  });

  it('displays file info when file selected', () => {
    render(<DocumentUpload currentUser="user_a" />);
    selectFile(txtFile('test.txt'));
    expect(screen.getByText(/Selected: test.txt/)).toBeTruthy();
  });

  it('rejects unsupported files', () => {
    render(<DocumentUpload currentUser="user_a" />);
    selectFile(new File(['test'], 'test.exe', { type: 'application/x-msdownload' }));
    expect(screen.getByText(/Invalid file type/)).toBeTruthy();
  });

  it('rejects PDF files (no server-side PDF parsing)', () => {
    render(<DocumentUpload currentUser="user_a" />);
    selectFile(new File(['test'], 'policy.pdf', { type: 'application/pdf' }));
    expect(screen.getByText(/Invalid file type/)).toBeTruthy();
  });

  it('rejects files larger than 10MB', () => {
    render(<DocumentUpload currentUser="user_a" />);
    selectFile(txtFile('large.txt', 'x'.repeat(11 * 1024 * 1024)));
    expect(screen.getByText(/File too large/)).toBeTruthy();
  });

  it('accepts text files', () => {
    render(<DocumentUpload currentUser="user_a" />);
    selectFile(txtFile('policy.txt'));
    expect(screen.getByText(/Selected: policy.txt/)).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeFalsy();
  });

  it('accepts CSV files even when the browser reports an Excel MIME type', () => {
    render(<DocumentUpload currentUser="user_a" />);
    selectFile(new File(['a,b'], 'data.csv', { type: 'application/vnd.ms-excel' }));
    expect(screen.getByText(/Selected: data.csv/)).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeFalsy();
  });

  it('disables upload button without file', () => {
    render(<DocumentUpload currentUser="user_a" />);
    expect(screen.getByRole('button', { name: 'Upload' })).toHaveAttribute('disabled');
  });

  it('enables upload button with valid file', () => {
    render(<DocumentUpload currentUser="user_a" />);
    selectFile(txtFile());
    expect(screen.getByRole('button', { name: 'Upload' })).not.toHaveAttribute('disabled');
  });

  it('shows progress during upload', async () => {
    render(<DocumentUpload currentUser="user_a" />);
    selectFile(txtFile());
    await clickUploadAndWaitForSend();

    const progressCallback = mockXhr.upload.addEventListener.mock.calls.find(
      (call) => call[0] === 'progress'
    )?.[1];
    expect(progressCallback).toBeTruthy();

    progressCallback({ lengthComputable: true, loaded: 50, total: 100 });

    await waitFor(() => {
      expect(screen.getByText('50%')).toBeTruthy();
    });
  });

  it('handles successful upload', async () => {
    const onUploadSuccess = vi.fn();
    render(<DocumentUpload currentUser="user_a" onUploadSuccess={onUploadSuccess} />);
    selectFile(txtFile());
    await clickUploadAndWaitForSend();

    mockXhr.status = 200;
    mockXhr.onload();

    await waitFor(() => {
      expect(screen.getByText(/uploaded successfully/)).toBeTruthy();
      expect(onUploadSuccess).toHaveBeenCalled();
    });
  });

  it('handles upload error', async () => {
    render(<DocumentUpload currentUser="user_a" />);
    selectFile(txtFile());
    await clickUploadAndWaitForSend();

    mockXhr.status = 500;
    mockXhr.statusText = 'Internal Server Error';
    mockXhr.responseText = '{"detail": "File upload failed"}';
    mockXhr.onload();

    await waitFor(() => {
      expect(screen.getByText(/File upload failed/)).toBeTruthy();
    });
  });

  it('handles network error', async () => {
    render(<DocumentUpload currentUser="user_a" />);
    selectFile(txtFile());
    await clickUploadAndWaitForSend();

    mockXhr.onerror();

    await waitFor(() => {
      expect(screen.getByText(/Network error/)).toBeTruthy();
    });
  });

  it('handles upload abort', async () => {
    render(<DocumentUpload currentUser="user_a" />);
    selectFile(txtFile());
    await clickUploadAndWaitForSend();

    mockXhr.onabort();

    await waitFor(() => {
      expect(screen.getByText(/cancelled/)).toBeTruthy();
    });
  });

  it('clears form on clear button click', () => {
    render(<DocumentUpload currentUser="user_a" />);
    selectFile(txtFile());
    expect(screen.getByText(/Selected: test.txt/)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));

    expect(screen.queryByText(/Selected:/)).toBeFalsy();
  });

  it('disables buttons during upload', async () => {
    render(<DocumentUpload currentUser="user_a" />);
    const fileInput = selectFile(txtFile());

    const uploadButton = screen.getByRole('button', { name: 'Upload' });
    fireEvent.click(uploadButton);

    expect(uploadButton).toHaveAttribute('disabled');
    expect(screen.getByRole('button', { name: 'Clear' })).toHaveAttribute('disabled');
    expect(fileInput).toHaveAttribute('disabled');

    // Let the pending file read finish so it cannot leak into the next test
    await waitFor(() => expect(xhrSend).toHaveBeenCalled());
  });

  it('POSTs JSON to /api/documents/upload with the X-User-ID header', async () => {
    render(<DocumentUpload currentUser="user_b" />);
    selectFile(txtFile('policy.txt', 'Laptops must use disk encryption.'));
    await clickUploadAndWaitForSend();

    expect(xhrOpen).toHaveBeenCalledWith(
      'POST',
      'http://localhost:8000/api/documents/upload',
      true
    );
    expect(xhrSetRequestHeader).toHaveBeenCalledWith('Content-Type', 'application/json');
    expect(xhrSetRequestHeader).toHaveBeenCalledWith('X-User-ID', 'user_b');
    expect(JSON.parse(xhrSend.mock.calls[0][0])).toEqual({
      filename: 'policy.txt',
      content: 'Laptops must use disk encryption.',
    });
  });

  it('rejects an empty file without calling the API', async () => {
    render(<DocumentUpload currentUser="user_a" />);
    selectFile(txtFile('empty.txt', '   '));
    fireEvent.click(screen.getByRole('button', { name: 'Upload' }));

    await waitFor(() => {
      expect(screen.getByText(/File is empty/)).toBeTruthy();
    });
    expect(xhrSend).not.toHaveBeenCalled();
  });

  it('clears form on successful upload', async () => {
    render(<DocumentUpload currentUser="user_a" />);
    selectFile(txtFile());
    expect(screen.getByText(/Selected: test.txt/)).toBeTruthy();
    await clickUploadAndWaitForSend();

    mockXhr.status = 200;
    mockXhr.onload();

    await waitFor(() => {
      expect(screen.queryByText(/Selected:/)).toBeFalsy();
    });
  });

  it('displays upload info text', () => {
    render(<DocumentUpload currentUser="user_a" />);
    expect(screen.getByText('Supported: TXT, CSV')).toBeTruthy();
    expect(screen.getByText('Max size: 10MB')).toBeTruthy();
  });
});
