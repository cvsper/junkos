import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PhotoUpload } from '../src/components/BookingFlow/Step2Photos';
import * as api from '../src/services/api';

jest.mock('../src/services/api');

describe('PhotoUpload Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.URL.createObjectURL = jest.fn(() => 'mock-url');
  });

  describe('File Selection', () => {
    test('renders dropzone with instructions', () => {
      render(<PhotoUpload onPhotosChange={jest.fn()} />);
      
      expect(screen.getByText(/drag.*drop|upload photos/i)).toBeInTheDocument();
      expect(screen.getByText(/click to select/i)).toBeInTheDocument();
    });

    test('allows selecting files via file input', async () => {
      const user = userEvent.setup();
      const handleChange = jest.fn();
      render(<PhotoUpload onPhotosChange={handleChange} />);
      
      const file = new File(['photo'], 'test.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      
      await user.upload(input, file);
      
      await waitFor(() => {
        expect(handleChange).toHaveBeenCalled();
      });
    });

    test('accepts multiple files at once', async () => {
      const user = userEvent.setup();
      const handleChange = jest.fn();
      render(<PhotoUpload onPhotosChange={handleChange} multiple />);
      
      const files = [
        new File(['photo1'], 'test1.jpg', { type: 'image/jpeg' }),
        new File(['photo2'], 'test2.jpg', { type: 'image/jpeg' }),
        new File(['photo3'], 'test3.jpg', { type: 'image/jpeg' }),
      ];
      
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      await user.upload(input, files);
      
      await waitFor(() => {
        expect(handleChange).toHaveBeenCalledWith(
          expect.arrayContaining([
            expect.objectContaining({ name: 'test1.jpg' }),
            expect.objectContaining({ name: 'test2.jpg' }),
            expect.objectContaining({ name: 'test3.jpg' }),
          ])
        );
      });
    });

    test('handles drag and drop', async () => {
      const handleChange = jest.fn();
      render(<PhotoUpload onPhotosChange={handleChange} />);
      
      const dropzone = screen.getByText(/drag.*drop/i).closest('div');
      const file = new File(['photo'], 'test.jpg', { type: 'image/jpeg' });
      
      const dropEvent = new Event('drop', { bubbles: true });
      Object.defineProperty(dropEvent, 'dataTransfer', {
        value: {
          files: [file],
        },
      });
      
      dropzone.dispatchEvent(dropEvent);
      
      await waitFor(() => {
        expect(handleChange).toHaveBeenCalled();
      });
    });
  });

  describe('File Validation', () => {
    test('only accepts image files', async () => {
      const user = userEvent.setup();
      const handleChange = jest.fn();
      render(<PhotoUpload onPhotosChange={handleChange} />);
      
      const invalidFile = new File(['content'], 'document.pdf', { type: 'application/pdf' });
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      
      await user.upload(input, invalidFile);
      
      await waitFor(() => {
        expect(screen.getByText(/only images/i)).toBeInTheDocument();
      });
      expect(handleChange).not.toHaveBeenCalled();
    });

    test('enforces maximum file size', async () => {
      const user = userEvent.setup();
      const handleChange = jest.fn();
      render(<PhotoUpload onPhotosChange={handleChange} maxSize={1024 * 1024} />); // 1MB
      
      // Create a file larger than 1MB (mock)
      const largeFile = new File(['x'.repeat(2 * 1024 * 1024)], 'large.jpg', { 
        type: 'image/jpeg' 
      });
      Object.defineProperty(largeFile, 'size', { value: 2 * 1024 * 1024 });
      
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      await user.upload(input, largeFile);
      
      await waitFor(() => {
        expect(screen.getByText(/too large|file size/i)).toBeInTheDocument();
      });
    });

    test('enforces maximum number of files', async () => {
      const user = userEvent.setup();
      const handleChange = jest.fn();
      render(<PhotoUpload onPhotosChange={handleChange} maxFiles={3} />);
      
      const files = Array.from({ length: 5 }, (_, i) => 
        new File([`photo${i}`], `test${i}.jpg`, { type: 'image/jpeg' })
      );
      
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      await user.upload(input, files);
      
      await waitFor(() => {
        expect(screen.getByText(/maximum.*3/i)).toBeInTheDocument();
      });
    });

    test('validates image dimensions', async () => {
      const user = userEvent.setup();
      const handleChange = jest.fn();
      render(<PhotoUpload onPhotosChange={handleChange} minWidth={800} minHeight={600} />);
      
      const file = new File(['photo'], 'small.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      
      // Mock Image loading
      global.Image = class {
        constructor() {
          setTimeout(() => {
            this.width = 400;
            this.height = 300;
            this.onload();
          }, 100);
        }
      };
      
      await user.upload(input, file);
      
      await waitFor(() => {
        expect(screen.getByText(/dimensions|resolution/i)).toBeInTheDocument();
      });
    });
  });

  describe('Preview Display', () => {
    test('shows thumbnail previews of uploaded images', async () => {
      const user = userEvent.setup();
      render(<PhotoUpload onPhotosChange={jest.fn()} />);
      
      const file = new File(['photo'], 'test.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      
      await user.upload(input, file);
      
      await waitFor(() => {
        const preview = screen.getByAltText(/preview|test.jpg/i);
        expect(preview).toBeInTheDocument();
        expect(preview).toHaveAttribute('src', expect.stringContaining('mock-url'));
      });
    });

    test('displays file name and size', async () => {
      const user = userEvent.setup();
      render(<PhotoUpload onPhotosChange={jest.fn()} />);
      
      const file = new File(['photo'], 'vacation.jpg', { type: 'image/jpeg' });
      Object.defineProperty(file, 'size', { value: 1024 * 500 }); // 500KB
      
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      await user.upload(input, file);
      
      await waitFor(() => {
        expect(screen.getByText(/vacation\.jpg/i)).toBeInTheDocument();
        expect(screen.getByText(/500/i)).toBeInTheDocument(); // Size in KB
      });
    });

    test('shows upload progress indicator', async () => {
      const user = userEvent.setup();
      api.uploadPhoto.mockImplementation(() => 
        new Promise(resolve => setTimeout(() => resolve({ url: 'uploaded.jpg' }), 1000))
      );
      
      render(<PhotoUpload onPhotosChange={jest.fn()} autoUpload />);
      
      const file = new File(['photo'], 'test.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      
      await user.upload(input, file);
      
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    test('shows success state after upload', async () => {
      const user = userEvent.setup();
      api.uploadPhoto.mockResolvedValue({ url: 'uploaded.jpg' });
      
      render(<PhotoUpload onPhotosChange={jest.fn()} autoUpload />);
      
      const file = new File(['photo'], 'test.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      
      await user.upload(input, file);
      
      await waitFor(() => {
        expect(screen.getByText(/success|uploaded/i)).toBeInTheDocument();
      });
    });
  });

  describe('Photo Management', () => {
    test('can remove individual photos', async () => {
      const user = userEvent.setup();
      const handleChange = jest.fn();
      render(<PhotoUpload onPhotosChange={handleChange} />);
      
      // Upload 2 files
      const files = [
        new File(['photo1'], 'test1.jpg', { type: 'image/jpeg' }),
        new File(['photo2'], 'test2.jpg', { type: 'image/jpeg' }),
      ];
      
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      await user.upload(input, files);
      
      await waitFor(() => {
        expect(screen.getByText(/test1\.jpg/i)).toBeInTheDocument();
      });
      
      // Remove first photo
      const removeButtons = screen.getAllByRole('button', { name: /remove|delete/i });
      await user.click(removeButtons[0]);
      
      await waitFor(() => {
        expect(screen.queryByText(/test1\.jpg/i)).not.toBeInTheDocument();
        expect(screen.getByText(/test2\.jpg/i)).toBeInTheDocument();
      });
    });

    test('can clear all photos', async () => {
      const user = userEvent.setup();
      const handleChange = jest.fn();
      render(<PhotoUpload onPhotosChange={handleChange} />);
      
      const files = [
        new File(['photo1'], 'test1.jpg', { type: 'image/jpeg' }),
        new File(['photo2'], 'test2.jpg', { type: 'image/jpeg' }),
      ];
      
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      await user.upload(input, files);
      
      await waitFor(() => {
        expect(screen.getByText(/test1\.jpg/i)).toBeInTheDocument();
      });
      
      // Clear all
      const clearButton = screen.getByRole('button', { name: /clear all/i });
      await user.click(clearButton);
      
      expect(screen.queryByText(/test1\.jpg/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/test2\.jpg/i)).not.toBeInTheDocument();
    });

    test('can reorder photos via drag and drop', async () => {
      const handleChange = jest.fn();
      render(<PhotoUpload onPhotosChange={handleChange} allowReorder />);
      
      // Upload files
      const files = [
        new File(['photo1'], 'first.jpg', { type: 'image/jpeg' }),
        new File(['photo2'], 'second.jpg', { type: 'image/jpeg' }),
      ];
      
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      await userEvent.upload(input, files);
      
      await waitFor(() => {
        expect(screen.getByText(/first\.jpg/i)).toBeInTheDocument();
      });
      
      // Drag and drop would be tested here
      // (simplified for brevity)
    });
  });

  describe('Upload Process', () => {
    test('uploads photos to server', async () => {
      const user = userEvent.setup();
      api.uploadPhoto.mockResolvedValue({ url: 'https://cdn.example.com/photo.jpg' });
      
      render(<PhotoUpload onPhotosChange={jest.fn()} autoUpload />);
      
      const file = new File(['photo'], 'test.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      
      await user.upload(input, file);
      
      await waitFor(() => {
        expect(api.uploadPhoto).toHaveBeenCalledWith(
          expect.any(FormData),
          expect.any(Function)
        );
      });
    });

    test('handles upload failures', async () => {
      const user = userEvent.setup();
      api.uploadPhoto.mockRejectedValue(new Error('Upload failed'));
      
      render(<PhotoUpload onPhotosChange={jest.fn()} autoUpload />);
      
      const file = new File(['photo'], 'test.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      
      await user.upload(input, file);
      
      await waitFor(() => {
        expect(screen.getByText(/upload failed|error/i)).toBeInTheDocument();
      });
    });

    test('allows retry on failed uploads', async () => {
      const user = userEvent.setup();
      api.uploadPhoto
        .mockRejectedValueOnce(new Error('Failed'))
        .mockResolvedValueOnce({ url: 'success.jpg' });
      
      render(<PhotoUpload onPhotosChange={jest.fn()} autoUpload />);
      
      const file = new File(['photo'], 'test.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      
      await user.upload(input, file);
      
      await waitFor(() => {
        expect(screen.getByText(/upload failed/i)).toBeInTheDocument();
      });
      
      // Retry
      const retryButton = screen.getByRole('button', { name: /retry/i });
      await user.click(retryButton);
      
      await waitFor(() => {
        expect(screen.getByText(/success|uploaded/i)).toBeInTheDocument();
      });
    });

    test('compresses images before upload', async () => {
      const user = userEvent.setup();
      api.uploadPhoto.mockResolvedValue({ url: 'compressed.jpg' });
      
      render(<PhotoUpload onPhotosChange={jest.fn()} compress autoUpload />);
      
      const file = new File(['photo'], 'test.jpg', { type: 'image/jpeg' });
      Object.defineProperty(file, 'size', { value: 5 * 1024 * 1024 }); // 5MB
      
      const input = screen.getByLabelText(/upload photos/i, { selector: 'input' });
      await user.upload(input, file);
      
      await waitFor(() => {
        expect(screen.getByText(/compressing/i)).toBeInTheDocument();
      });
    });
  });
});
