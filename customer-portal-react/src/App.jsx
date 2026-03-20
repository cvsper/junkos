import React from 'react';
import { AlertCircle } from 'lucide-react';
import Layout from './components/Layout';
import ProgressBar from './components/ProgressBar';
import Step1Address from './components/BookingFlow/Step1Address';
import Step2Photos from './components/BookingFlow/Step2Photos';
import Step3Items from './components/BookingFlow/Step3Items';
import Step4DateTime from './components/BookingFlow/Step4DateTime';
import Step5Estimate from './components/BookingFlow/Step5Estimate';
import Step6Payment from './components/BookingFlow/Step6Payment';
import { useBookingForm } from './hooks/useBookingForm';

function App() {
  const {
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
  } = useBookingForm();

  const renderStep = () => {
    const commonProps = {
      formData,
      updateFormData,
      updateCustomerInfo,
      nextStep,
      prevStep,
      setError,
      setIsLoading,
      isLoading,
    };

    switch (currentStep) {
      case 1:
        return <Step1Address {...commonProps} />;
      case 2:
        return <Step2Photos {...commonProps} />;
      case 3:
        return <Step3Items {...commonProps} />;
      case 4:
        return <Step4DateTime {...commonProps} />;
      case 5:
        return <Step5Estimate {...commonProps} />;
      case 6:
        return <Step6Payment {...commonProps} resetForm={resetForm} />;
      default:
        return <Step1Address {...commonProps} />;
    }
  };

  return (
    <Layout>
      {/* Hero Section - Only show on step 1 */}
      {currentStep === 1 && (
        <div className="text-center mb-8 animate-fade-in">
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            Easy Junk Removal in Minutes
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Schedule your pickup, get an instant estimate, and say goodbye to your junk.
            Professional service, transparent pricing.
          </p>
          <div className="mt-4 inline-flex items-center gap-2 bg-green-50 border border-green-200 rounded-full px-5 py-2 text-sm text-green-800 font-medium">
            <span>&#9851;&#65039;</span>
            We donate &amp; recycle first — landfill is always the last resort
          </div>
        </div>
      )}

      {/* Progress Bar */}
      <ProgressBar currentStep={currentStep} onStepClick={goToStep} />

      {/* Error Message */}
      {error && (
        <div className="mb-6 bg-red-50 border-2 border-red-200 rounded-lg p-4 animate-slide-up">
          <div className="flex gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="font-medium text-red-900">Error</p>
              <p className="text-sm text-red-800 mt-1">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-600 hover:text-red-800 font-medium text-sm"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Current Step */}
      <div className="mb-8">
        {renderStep()}
      </div>

      {/* Trust Indicators - Show on steps 1-3 */}
      {currentStep <= 3 && (
        <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-5 animate-fade-in">
          <div className="text-center p-5 bg-white rounded-lg border border-gray-200">
            <div className="text-3xl mb-2">&#9889;</div>
            <h3 className="font-semibold text-gray-900 mb-1">Same-Day Service</h3>
            <p className="text-sm text-gray-600">
              Available for urgent pickups in most areas
            </p>
          </div>

          <div className="text-center p-5 bg-white rounded-lg border border-gray-200">
            <div className="text-3xl mb-2">&#128176;</div>
            <h3 className="font-semibold text-gray-900 mb-1">Up to 40% Less</h3>
            <p className="text-sm text-gray-600">
              Transparent pricing, way below the big guys
            </p>
          </div>

          <div className="text-center p-5 bg-green-50 rounded-lg border border-green-200">
            <div className="text-3xl mb-2">&#10084;&#65039;</div>
            <h3 className="font-semibold text-green-900 mb-1">Donate First</h3>
            <p className="text-sm text-green-800">
              Usable items go to local charities &amp; shelters before the landfill
            </p>
          </div>

          <div className="text-center p-5 bg-green-50 rounded-lg border border-green-200">
            <div className="text-3xl mb-2">&#9851;&#65039;</div>
            <h3 className="font-semibold text-green-900 mb-1">Recycle &amp; Reuse</h3>
            <p className="text-sm text-green-800">
              We sort, recycle, and responsibly dispose — donation receipts provided
            </p>
          </div>
        </div>
      )}

      {/* Customer Reviews - Show on step 5 */}
      {currentStep === 5 && (
        <div className="mt-12 bg-white rounded-lg border border-gray-200 p-8 animate-fade-in">
          <h3 className="text-2xl font-bold text-gray-900 mb-6 text-center">
            What Our Customers Say
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="border-l-4 border-primary-500 pl-4">
              <div className="flex gap-1 mb-2">
                {[...Array(5)].map((_, i) => (
                  <span key={i} className="text-yellow-400">⭐</span>
                ))}
              </div>
              <p className="text-gray-700 mb-3">
                "Super easy to book and the crew was professional and fast. Got rid of all my old furniture in under an hour!"
              </p>
              <p className="text-sm font-medium text-gray-900">- Sarah M.</p>
            </div>
            
            <div className="border-l-4 border-primary-500 pl-4">
              <div className="flex gap-1 mb-2">
                {[...Array(5)].map((_, i) => (
                  <span key={i} className="text-yellow-400">⭐</span>
                ))}
              </div>
              <p className="text-gray-700 mb-3">
                "Fair pricing and excellent service. They even swept up after loading the truck. Highly recommend!"
              </p>
              <p className="text-sm font-medium text-gray-900">- James T.</p>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}

export default App;
