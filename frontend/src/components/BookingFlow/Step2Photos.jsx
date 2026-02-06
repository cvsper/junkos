import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Camera, Upload, X, AlertCircle, Loader, Image as ImageIcon } from 'lucide-react';
import { validatePhotos } from '../../utils/validation';
import { api } from '../../services/api';

const Step2Photos = ({ formData, updateFormData, nextStep, prevStep, setError, setIsLoading, isLoading }) => {
  const [photos, setPhotos] = useState(formData.photos || []);
  const [previews, setPreviews] = useState(formData.photoUrls || []);
  const [validationError, setValidationError] = useState('');
  const [uploadProgress, setUploadProgress] = useState(false);

  const onDrop = useCallback((acceptedFiles) => {
    setValidationError('');
    
    const newPhotos = [...photos, ...acceptedFiles];
    const error = validatePhotos(newPhotos);
    
    if (error) {
      setValidationError(error);
      return;
    }

    setPhotos(newPhotos);

    // Create preview URLs
    const newPreviews = acceptedFiles.map((file) => URL.createObjectURL(file));
    setPreviews([...previews, ...newPreviews]);
  }, [photos, previews]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.webp'],
    },
    maxFiles: 10,
    disabled: isLoading,
  });

  const removePhoto = (index) => {
    const newPhotos = photos.filter((_, i) => i !== index);
    const newPreviews = previews.filter((_, i) => i !== index);
    
    // Revoke the object URL to free memory
    URL.revokeObjectURL(previews[index]);
    
    setPhotos(newPhotos);
    setPreviews(newPreviews);
    setValidationError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const error = validatePhotos(photos);
    if (error) {
      setValidationError(error);
      return;
    }

    setIsLoading(true);
    setUploadProgress(true);
    setError(null);

    try {
      // Upload photos to backend
      const uploadResult = await api.uploadPhotos(photos);
      
      updateFormData('photos', photos);
      updateFormData('photoUrls', uploadResult.urls || previews);
      
      nextStep();
    } catch (err) {
      setError(err.message || 'Failed to upload photos. Please try again.');
    } finally {
      setIsLoading(false);
      setUploadProgress(false);
    }
  };

  const handleSkip = () => {
    updateFormData('photos', []);
    updateFormData('photoUrls', []);
    nextStep();
  };

  return (
    <div className="card animate-fade-in">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="bg-primary-100 p-2 rounded-lg">
            <Camera className="w-6 h-6 text-primary-600" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">Show us the junk</h2>
        </div>
        <p className="text-gray-600">
          Upload photos to help us provide an accurate estimate. (Optional but recommended)
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Dropzone */}
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
            isDragActive
              ? 'border-primary-500 bg-primary-50'
              : 'border-gray-300 hover:border-primary-400 bg-gray-50'
          } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          <input {...getInputProps()} />
          <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          {isDragActive ? (
            <p className="text-primary-600 font-medium">Drop the photos here...</p>
          ) : (
            <>
              <p className="text-gray-700 font-medium mb-2">
                Drag & drop photos here, or click to select
              </p>
              <p className="text-sm text-gray-500">
                Max 10 photos • JPG, PNG, or WebP • Up to 10MB each
              </p>
            </>
          )}
        </div>

        {validationError && (
          <div className="error-message">
            <AlertCircle className="w-4 h-4" />
            <span>{validationError}</span>
          </div>
        )}

        {/* Photo Previews */}
        {previews.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">
              Uploaded Photos ({previews.length}/10)
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {previews.map((preview, index) => (
                <div key={index} className="relative group">
                  <img
                    src={preview}
                    alt={`Preview ${index + 1}`}
                    className="w-full h-32 object-cover rounded-lg border border-gray-200"
                  />
                  <button
                    type="button"
                    onClick={() => removePhoto(index)}
                    disabled={isLoading}
                    className="absolute top-2 right-2 bg-red-500 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600 disabled:opacity-50"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tips */}
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex gap-3">
            <ImageIcon className="w-5 h-5 text-green-600 mt-0.5" />
            <div className="text-sm text-green-900">
              <p className="font-medium mb-1">Photo Tips</p>
              <ul className="list-disc list-inside space-y-1 text-green-800">
                <li>Take photos from multiple angles</li>
                <li>Include the entire pile or area</li>
                <li>Good lighting helps us see details</li>
                <li>Show items that need special handling</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Navigation Buttons */}
        <div className="flex justify-between pt-4 gap-4">
          <button
            type="button"
            onClick={prevStep}
            disabled={isLoading}
            className="btn-secondary"
          >
            ← Back
          </button>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={handleSkip}
              disabled={isLoading}
              className="text-gray-600 hover:text-gray-800 font-medium px-4"
            >
              Skip for now
            </button>
            <button
              type="submit"
              disabled={isLoading || photos.length === 0}
              className="btn-primary flex items-center gap-2"
            >
              {uploadProgress ? (
                <>
                  <Loader className="w-5 h-5 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  Continue
                  <span>→</span>
                </>
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
};

export default Step2Photos;
