import { useState } from 'react';

const initialFormData = {
  address: '',
  addressDetails: null,
  photos: [],
  photoUrls: [],
  itemDescription: '',
  quantity: 1,
  selectedDate: null,
  selectedTime: '',
  estimate: null,
  customerInfo: {
    name: '',
    email: '',
    phone: '',
  },
};

export const useBookingForm = () => {
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState(initialFormData);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const totalSteps = 6;

  const updateFormData = (field, value) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const updateCustomerInfo = (field, value) => {
    setFormData((prev) => ({
      ...prev,
      customerInfo: {
        ...prev.customerInfo,
        [field]: value,
      },
    }));
  };

  const nextStep = () => {
    if (currentStep < totalSteps) {
      setCurrentStep((prev) => prev + 1);
      setError(null);
    }
  };

  const prevStep = () => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1);
      setError(null);
    }
  };

  const goToStep = (step) => {
    if (step >= 1 && step <= totalSteps) {
      setCurrentStep(step);
      setError(null);
    }
  };

  const resetForm = () => {
    setFormData(initialFormData);
    setCurrentStep(1);
    setError(null);
    setIsLoading(false);
  };

  return {
    currentStep,
    totalSteps,
    formData,
    isLoading,
    error,
    setIsLoading,
    setError,
    updateFormData,
    updateCustomerInfo,
    nextStep,
    prevStep,
    goToStep,
    resetForm,
  };
};
