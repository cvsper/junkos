import React, { useState, useEffect } from 'react';
import { DollarSign, MapPin, Calendar, Package, Loader, AlertCircle, CheckCircle } from 'lucide-react';
import { api } from '../../services/api';
import { formatCurrency } from '../../utils/validation';
import { format } from 'date-fns';

const Step5Estimate = ({ formData, updateFormData, nextStep, prevStep, setError, setIsLoading, isLoading }) => {
  const [estimate, setEstimate] = useState(formData.estimate || null);
  const [loadingEstimate, setLoadingEstimate] = useState(false);
  const [accepted, setAccepted] = useState(false);

  useEffect(() => {
    if (!estimate) {
      fetchEstimate();
    }
  }, []);

  const fetchEstimate = async () => {
    setLoadingEstimate(true);
    setError(null);

    try {
      const estimateData = {
        address: formData.address,
        itemCategory: formData.itemCategory,
        itemDescription: formData.itemDescription,
        quantity: formData.quantity,
        selectedDate: formData.selectedDate,
        selectedTime: formData.selectedTime,
        photoCount: formData.photos?.length || 0,
      };

      const result = await api.getPriceEstimate(estimateData);
      
      setEstimate(result.estimate);
      updateFormData('estimate', result.estimate);
    } catch (err) {
      // Fallback estimate calculation
      const basePrice = 150;
      const quantityPrice = (formData.quantity - 1) * 50;
      const categoryMultiplier = formData.itemCategory === 'appliances' ? 1.2 : 1;
      const total = (basePrice + quantityPrice) * categoryMultiplier;

      const fallbackEstimate = {
        subtotal: total,
        serviceFee: total * 0.1,
        tax: total * 0.08,
        total: total * 1.18,
        estimatedDuration: '1-2 hours',
        truckSize: formData.quantity > 5 ? 'Large Truck' : 'Standard Truck',
      };

      setEstimate(fallbackEstimate);
      updateFormData('estimate', fallbackEstimate);
      
      console.error('Failed to fetch estimate from API:', err);
    } finally {
      setLoadingEstimate(false);
    }
  };

  const handleAccept = () => {
    setAccepted(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!accepted) {
      setError('Please review and accept the estimate to continue');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await new Promise((resolve) => setTimeout(resolve, 500));
      nextStep();
    } catch (err) {
      setError('Failed to process estimate. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  if (loadingEstimate) {
    return (
      <div className="card animate-fade-in">
        <div className="flex flex-col items-center justify-center py-16">
          <Loader className="w-12 h-12 animate-spin text-primary-600 mb-4" />
          <p className="text-lg font-medium text-gray-900 mb-2">Calculating your estimate...</p>
          <p className="text-sm text-gray-600">This will just take a moment</p>
        </div>
      </div>
    );
  }

  const TIME_SLOTS = [
    { value: '08:00', label: '8:00 AM - 10:00 AM' },
    { value: '10:00', label: '10:00 AM - 12:00 PM' },
    { value: '12:00', label: '12:00 PM - 2:00 PM' },
    { value: '14:00', label: '2:00 PM - 4:00 PM' },
    { value: '16:00', label: '4:00 PM - 6:00 PM' },
  ];

  return (
    <div className="card animate-fade-in">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="bg-primary-100 p-2 rounded-lg">
            <DollarSign className="w-6 h-6 text-primary-600" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">Your Estimate</h2>
        </div>
        <p className="text-gray-600">
          Based on the information provided, here's your estimated cost.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Booking Summary */}
        <div className="bg-gray-50 rounded-lg p-5 space-y-4">
          <h3 className="font-semibold text-gray-900 mb-3">Booking Summary</h3>
          
          <div className="flex items-start gap-3">
            <MapPin className="w-5 h-5 text-gray-400 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-700">Location</p>
              <p className="text-sm text-gray-600">{formData.address}</p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <Calendar className="w-5 h-5 text-gray-400 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-700">Scheduled For</p>
              <p className="text-sm text-gray-600">
                {format(formData.selectedDate, 'EEEE, MMMM d, yyyy')} at{' '}
                {TIME_SLOTS.find(slot => slot.value === formData.selectedTime)?.label}
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <Package className="w-5 h-5 text-gray-400 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-700">Items</p>
              <p className="text-sm text-gray-600">
                {formData.quantity} item(s) - {formData.itemCategory?.replace('-', ' ')}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {formData.itemDescription?.substring(0, 100)}
                {formData.itemDescription?.length > 100 ? '...' : ''}
              </p>
            </div>
          </div>
        </div>

        {/* Price Breakdown */}
        {estimate && (
          <div className="border-2 border-primary-200 rounded-lg p-5">
            <h3 className="font-semibold text-gray-900 mb-4">Price Breakdown</h3>
            
            <div className="space-y-3">
              <div className="flex justify-between text-gray-700">
                <span>Service Fee</span>
                <span>{formatCurrency(estimate.subtotal)}</span>
              </div>
              
              {estimate.serviceFee > 0 && (
                <div className="flex justify-between text-gray-700">
                  <span>Environmental Fee</span>
                  <span>{formatCurrency(estimate.serviceFee)}</span>
                </div>
              )}
              
              <div className="flex justify-between text-gray-700">
                <span>Tax</span>
                <span>{formatCurrency(estimate.tax)}</span>
              </div>

              <div className="border-t-2 border-gray-300 pt-3 mt-3">
                <div className="flex justify-between items-center">
                  <span className="text-xl font-bold text-gray-900">Total</span>
                  <span className="text-2xl font-bold text-primary-600">
                    {formatCurrency(estimate.total)}
                  </span>
                </div>
              </div>

              <div className="flex justify-between text-sm text-gray-600 pt-2">
                <span>Estimated Duration</span>
                <span className="font-medium">{estimate.estimatedDuration}</span>
              </div>
              
              <div className="flex justify-between text-sm text-gray-600">
                <span>Truck Size</span>
                <span className="font-medium">{estimate.truckSize}</span>
              </div>
            </div>
          </div>
        )}

        {/* Important Notes */}
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex gap-3">
            <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5" />
            <div className="text-sm text-yellow-900">
              <p className="font-medium mb-2">Please Note:</p>
              <ul className="list-disc list-inside space-y-1 text-yellow-800">
                <li>This is an <strong>estimate</strong> based on your description</li>
                <li>Final price may vary based on actual volume and labor required</li>
                <li>We'll provide a final quote before starting the job</li>
                <li>No hidden fees - you only pay for what we remove</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Acceptance Checkbox */}
        <div className="bg-white border-2 border-gray-200 rounded-lg p-4">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={accepted}
              onChange={(e) => setAccepted(e.target.checked)}
              disabled={isLoading}
              className="mt-1 w-5 h-5 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
            />
            <div className="flex-1">
              <p className="font-medium text-gray-900">
                I understand and accept this estimate
              </p>
              <p className="text-sm text-gray-600 mt-1">
                I understand that the final price may vary based on the actual job requirements.
                I agree to receive a final quote on-site before the work begins.
              </p>
            </div>
          </label>
        </div>

        {/* Success Message */}
        {accepted && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 animate-slide-up">
            <div className="flex gap-3">
              <CheckCircle className="w-5 h-5 text-green-600 mt-0.5" />
              <div className="text-sm text-green-900">
                <p className="font-medium">Great! You're almost done.</p>
                <p className="text-green-800 mt-1">
                  Proceed to payment to confirm your booking.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="flex justify-between pt-4">
          <button
            type="button"
            onClick={prevStep}
            disabled={isLoading}
            className="btn-secondary"
          >
            ← Back
          </button>
          <button
            type="submit"
            disabled={isLoading || !accepted}
            className="btn-primary flex items-center gap-2"
          >
            {isLoading ? (
              <>
                <Loader className="w-5 h-5 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                Proceed to Payment
                <span>→</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default Step5Estimate;
