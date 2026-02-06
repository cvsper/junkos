import React, { useState, useEffect } from 'react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import { Calendar, Clock, AlertCircle, Loader } from 'lucide-react';
import { validateDateTime } from '../../utils/validation';
import { api } from '../../services/api';
import { format, addDays, setHours, setMinutes } from 'date-fns';

const TIME_SLOTS = [
  { value: '08:00', label: '8:00 AM - 10:00 AM' },
  { value: '10:00', label: '10:00 AM - 12:00 PM' },
  { value: '12:00', label: '12:00 PM - 2:00 PM' },
  { value: '14:00', label: '2:00 PM - 4:00 PM' },
  { value: '16:00', label: '4:00 PM - 6:00 PM' },
];

const Step4DateTime = ({ formData, updateFormData, nextStep, prevStep, setError, setIsLoading, isLoading }) => {
  const [selectedDate, setSelectedDate] = useState(formData.selectedDate || null);
  const [selectedTime, setSelectedTime] = useState(formData.selectedTime || '');
  const [availableSlots, setAvailableSlots] = useState([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [validationError, setValidationError] = useState('');

  const minDate = addDays(new Date(), 1); // Minimum 24 hours advance
  const maxDate = addDays(new Date(), 90); // Book up to 90 days ahead

  useEffect(() => {
    if (selectedDate) {
      fetchAvailableSlots(selectedDate);
    }
  }, [selectedDate]);

  const fetchAvailableSlots = async (date) => {
    setLoadingSlots(true);
    try {
      const result = await api.getAvailableSlots(date);
      setAvailableSlots(result.availableSlots || TIME_SLOTS.map(slot => slot.value));
    } catch (err) {
      // Fallback to all slots if API fails
      setAvailableSlots(TIME_SLOTS.map(slot => slot.value));
      console.error('Failed to fetch available slots:', err);
    } finally {
      setLoadingSlots(false);
    }
  };

  const handleDateChange = (date) => {
    setSelectedDate(date);
    setSelectedTime(''); // Reset time when date changes
    setValidationError('');
  };

  const handleTimeSelect = (time) => {
    setSelectedTime(time);
    setValidationError('');
  };

  const isWeekday = (date) => {
    const day = date.getDay();
    return day !== 0 && day !== 6; // Disable weekends if needed
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const error = validateDateTime(selectedDate, selectedTime);
    if (error) {
      setValidationError(error);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      updateFormData('selectedDate', selectedDate);
      updateFormData('selectedTime', selectedTime);

      // Simulate processing
      await new Promise((resolve) => setTimeout(resolve, 500));

      nextStep();
    } catch (err) {
      setError('Failed to save scheduling information. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="card animate-fade-in">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="bg-primary-100 p-2 rounded-lg">
            <Calendar className="w-6 h-6 text-primary-600" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">When should we come?</h2>
        </div>
        <p className="text-gray-600">
          Choose a convenient date and time for your junk removal.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Date Picker */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Select Date
          </label>
          <div className="relative">
            <DatePicker
              selected={selectedDate}
              onChange={handleDateChange}
              minDate={minDate}
              maxDate={maxDate}
              filterDate={isWeekday}
              inline
              disabled={isLoading}
              className="w-full"
            />
          </div>
        </div>

        {/* Time Slot Selection */}
        {selectedDate && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              <Clock className="inline w-4 h-4 mr-2" />
              Select Time Window
            </label>
            {loadingSlots ? (
              <div className="flex items-center justify-center py-8">
                <Loader className="w-6 h-6 animate-spin text-primary-600" />
                <span className="ml-2 text-gray-600">Checking availability...</span>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {TIME_SLOTS.map((slot) => {
                  const isAvailable = availableSlots.includes(slot.value);
                  const isSelected = selectedTime === slot.value;

                  return (
                    <button
                      key={slot.value}
                      type="button"
                      onClick={() => isAvailable && handleTimeSelect(slot.value)}
                      disabled={!isAvailable || isLoading}
                      className={`p-4 border-2 rounded-lg text-left transition-all ${
                        isSelected
                          ? 'border-primary-500 bg-primary-50'
                          : isAvailable
                          ? 'border-gray-200 hover:border-primary-300 bg-white'
                          : 'border-gray-100 bg-gray-50 cursor-not-allowed'
                      } ${isLoading ? 'opacity-50' : ''}`}
                    >
                      <div className="flex justify-between items-center">
                        <span className={`font-medium ${
                          isAvailable ? 'text-gray-900' : 'text-gray-400'
                        }`}>
                          {slot.label}
                        </span>
                        {!isAvailable && (
                          <span className="text-xs text-red-600 font-medium">
                            Unavailable
                          </span>
                        )}
                        {isSelected && (
                          <span className="text-primary-600">✓</span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {validationError && (
          <div className="error-message">
            <AlertCircle className="w-4 h-4" />
            <span>{validationError}</span>
          </div>
        )}

        {/* Selected Summary */}
        {selectedDate && selectedTime && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <div className="text-green-600 mt-0.5">✓</div>
              <div>
                <p className="font-medium text-green-900 mb-1">Appointment Selected</p>
                <p className="text-sm text-green-800">
                  {format(selectedDate, 'EEEE, MMMM d, yyyy')} at{' '}
                  {TIME_SLOTS.find(slot => slot.value === selectedTime)?.label}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Info Box */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex gap-3">
            <div className="text-blue-600 mt-0.5">ℹ️</div>
            <div className="text-sm text-blue-900">
              <p className="font-medium mb-1">Scheduling Notes</p>
              <ul className="list-disc list-inside space-y-1 text-blue-800">
                <li>Bookings require at least 24 hours advance notice</li>
                <li>Time windows are 2-hour arrival windows</li>
                <li>We'll send a reminder 24 hours before your appointment</li>
                <li>Need to reschedule? Contact us anytime!</li>
              </ul>
            </div>
          </div>
        </div>

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
            disabled={isLoading || !selectedDate || !selectedTime}
            className="btn-primary flex items-center gap-2"
          >
            {isLoading ? (
              <>
                <Loader className="w-5 h-5 animate-spin" />
                Processing...
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

export default Step4DateTime;
