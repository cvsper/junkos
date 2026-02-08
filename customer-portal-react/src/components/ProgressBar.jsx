import React from 'react';
import { Check } from 'lucide-react';
import clsx from 'clsx';

const steps = [
  { number: 1, name: 'Address' },
  { number: 2, name: 'Photos' },
  { number: 3, name: 'Items' },
  { number: 4, name: 'Schedule' },
  { number: 5, name: 'Estimate' },
  { number: 6, name: 'Payment' },
];

const ProgressBar = ({ currentStep, onStepClick }) => {
  const progress = ((currentStep - 1) / (steps.length - 1)) * 100;

  return (
    <div className="w-full py-6 px-4">
      {/* Mobile: Simple progress bar */}
      <div className="md:hidden">
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm font-medium text-gray-700">
            Step {currentStep} of {steps.length}
          </span>
          <span className="text-sm text-gray-500">
            {steps[currentStep - 1].name}
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-primary-600 h-2 rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Desktop: Full step indicators */}
      <div className="hidden md:block">
        <div className="relative">
          {/* Progress line */}
          <div className="absolute top-5 left-0 right-0 h-1 bg-gray-200">
            <div
              className="absolute top-0 left-0 h-full bg-primary-600 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Step circles */}
          <div className="relative flex justify-between">
            {steps.map((step) => {
              const isCompleted = currentStep > step.number;
              const isCurrent = currentStep === step.number;
              const isClickable = currentStep >= step.number;

              return (
                <button
                  key={step.number}
                  onClick={() => isClickable && onStepClick && onStepClick(step.number)}
                  disabled={!isClickable}
                  className={clsx(
                    'flex flex-col items-center group',
                    isClickable ? 'cursor-pointer' : 'cursor-not-allowed'
                  )}
                >
                  <div
                    className={clsx(
                      'w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200 border-2',
                      isCompleted && 'bg-primary-600 border-primary-600',
                      isCurrent && 'bg-white border-primary-600 ring-4 ring-primary-100',
                      !isCompleted && !isCurrent && 'bg-white border-gray-300'
                    )}
                  >
                    {isCompleted ? (
                      <Check className="w-5 h-5 text-white" />
                    ) : (
                      <span
                        className={clsx(
                          'text-sm font-semibold',
                          isCurrent ? 'text-primary-600' : 'text-gray-500'
                        )}
                      >
                        {step.number}
                      </span>
                    )}
                  </div>
                  <span
                    className={clsx(
                      'mt-2 text-xs font-medium transition-colors',
                      isCurrent ? 'text-primary-600' : 'text-gray-600',
                      isClickable && 'group-hover:text-primary-500'
                    )}
                  >
                    {step.name}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProgressBar;
