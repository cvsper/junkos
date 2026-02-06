import React, { useState, useEffect, useRef } from 'react';
import { MapPin, AlertCircle, Loader } from 'lucide-react';
import { validateAddress } from '../../utils/validation';

const Step1Address = ({ formData, updateFormData, nextStep, setError, setIsLoading, isLoading }) => {
  const [address, setAddress] = useState(formData.address || '');
  const [validationError, setValidationError] = useState('');
  const autocompleteRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    // Initialize Google Places Autocomplete
    const initAutocomplete = () => {
      if (window.google && window.google.maps && window.google.maps.places && inputRef.current) {
        autocompleteRef.current = new window.google.maps.places.Autocomplete(inputRef.current, {
          types: ['address'],
          componentRestrictions: { country: 'us' }, // Restrict to US addresses
        });

        autocompleteRef.current.addListener('place_changed', () => {
          const place = autocompleteRef.current.getPlace();
          if (place.formatted_address) {
            setAddress(place.formatted_address);
            setValidationError('');
            updateFormData('addressDetails', {
              formatted: place.formatted_address,
              placeId: place.place_id,
              location: {
                lat: place.geometry?.location?.lat(),
                lng: place.geometry?.location?.lng(),
              },
            });
          }
        });
      }
    };

    // Check if Google Maps is already loaded
    if (window.google) {
      initAutocomplete();
    } else {
      // Wait for Google Maps to load
      const checkGoogleMaps = setInterval(() => {
        if (window.google) {
          initAutocomplete();
          clearInterval(checkGoogleMaps);
        }
      }, 100);

      return () => clearInterval(checkGoogleMaps);
    }
  }, [updateFormData]);

  const handleAddressChange = (e) => {
    setAddress(e.target.value);
    setValidationError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    const error = validateAddress(address);
    if (error) {
      setValidationError(error);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // If Google Places wasn't used, do a basic validation
      if (!formData.addressDetails || formData.addressDetails.formatted !== address) {
        updateFormData('addressDetails', {
          formatted: address,
          placeId: null,
          location: null,
        });
      }
      
      updateFormData('address', address);
      
      // Simulate API call to validate service area
      await new Promise((resolve) => setTimeout(resolve, 800));
      
      nextStep();
    } catch (err) {
      setError('Failed to validate address. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="card animate-fade-in">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="bg-primary-100 p-2 rounded-lg">
            <MapPin className="w-6 h-6 text-primary-600" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">Where's the junk?</h2>
        </div>
        <p className="text-gray-600">
          Enter the address where we'll be picking up your items.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label htmlFor="address" className="block text-sm font-medium text-gray-700 mb-2">
            Service Address
          </label>
          <input
            ref={inputRef}
            type="text"
            id="address"
            value={address}
            onChange={handleAddressChange}
            placeholder="123 Main St, City, State ZIP"
            className="input-field"
            disabled={isLoading}
          />
          {validationError && (
            <div className="error-message">
              <AlertCircle className="w-4 h-4" />
              <span>{validationError}</span>
            </div>
          )}
          <p className="text-sm text-gray-500 mt-2">
            Start typing and select from the dropdown for best results
          </p>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex gap-3">
            <div className="text-blue-600 mt-0.5">ℹ️</div>
            <div className="text-sm text-blue-900">
              <p className="font-medium mb-1">Service Area Information</p>
              <p>
                We currently service residential and commercial properties in the greater metro area.
                We'll confirm availability at your location after you submit your address.
              </p>
            </div>
          </div>
        </div>

        <div className="flex justify-end pt-4">
          <button
            type="submit"
            disabled={isLoading || !address}
            className="btn-primary flex items-center gap-2"
          >
            {isLoading ? (
              <>
                <Loader className="w-5 h-5 animate-spin" />
                Validating...
              </>
            ) : (
              <>
                Continue
                <span>→</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default Step1Address;
