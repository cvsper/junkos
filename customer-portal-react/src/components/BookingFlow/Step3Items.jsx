import React, { useState } from 'react';
import { Package, AlertCircle, Loader } from 'lucide-react';
import { validateItemDescription, validateQuantity } from '../../utils/validation';

const ITEM_CATEGORIES = [
  { value: 'furniture', label: 'Furniture', icon: '🛋️' },
  { value: 'appliances', label: 'Appliances', icon: '🔌' },
  { value: 'electronics', label: 'Electronics', icon: '📺' },
  { value: 'construction', label: 'Construction Debris', icon: '🔨' },
  { value: 'yard-waste', label: 'Yard Waste', icon: '🌿' },
  { value: 'general', label: 'General Junk', icon: '🗑️' },
  { value: 'other', label: 'Other', icon: '📦' },
];

const Step3Items = ({ formData, updateFormData, nextStep, prevStep, setError, setIsLoading, isLoading }) => {
  const [description, setDescription] = useState(formData.itemDescription || '');
  const [quantity, setQuantity] = useState(formData.quantity || 1);
  const [selectedCategory, setSelectedCategory] = useState(formData.itemCategory || '');
  const [errors, setErrors] = useState({});

  const handleDescriptionChange = (e) => {
    setDescription(e.target.value);
    if (errors.description) {
      setErrors({ ...errors, description: '' });
    }
  };

  const handleQuantityChange = (e) => {
    const value = e.target.value;
    setQuantity(value);
    if (errors.quantity) {
      setErrors({ ...errors, quantity: '' });
    }
  };

  const handleCategorySelect = (category) => {
    setSelectedCategory(category);
    if (errors.category) {
      setErrors({ ...errors, category: '' });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const newErrors = {};

    // Validate category
    if (!selectedCategory) {
      newErrors.category = 'Please select a category';
    }

    // Validate description
    const descError = validateItemDescription(description);
    if (descError) {
      newErrors.description = descError;
    }

    // Validate quantity
    const qtyError = validateQuantity(quantity);
    if (qtyError) {
      newErrors.quantity = qtyError;
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      updateFormData('itemCategory', selectedCategory);
      updateFormData('itemDescription', description);
      updateFormData('quantity', parseInt(quantity, 10));

      // Simulate processing
      await new Promise((resolve) => setTimeout(resolve, 500));

      nextStep();
    } catch (err) {
      setError('Failed to save item details. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="card animate-fade-in">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="bg-primary-100 p-2 rounded-lg">
            <Package className="w-6 h-6 text-primary-600" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">What needs to go?</h2>
        </div>
        <p className="text-gray-600">
          Tell us about the items you need removed.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Category Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Item Category
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {ITEM_CATEGORIES.map((category) => (
              <button
                key={category.value}
                type="button"
                onClick={() => handleCategorySelect(category.value)}
                disabled={isLoading}
                className={`p-4 border-2 rounded-lg text-center transition-all ${
                  selectedCategory === category.value
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-gray-200 hover:border-primary-300 bg-white'
                } ${isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <div className="text-3xl mb-2">{category.icon}</div>
                <div className="text-sm font-medium text-gray-900">{category.label}</div>
              </button>
            ))}
          </div>
          {errors.category && (
            <div className="error-message mt-2">
              <AlertCircle className="w-4 h-4" />
              <span>{errors.category}</span>
            </div>
          )}
        </div>

        {/* Item Description */}
        <div>
          <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-2">
            Detailed Description
          </label>
          <textarea
            id="description"
            value={description}
            onChange={handleDescriptionChange}
            placeholder="E.g., Queen-sized mattress and box spring, old sofa with fabric tears, broken washing machine..."
            rows={5}
            maxLength={500}
            disabled={isLoading}
            className="input-field resize-none"
          />
          <div className="flex justify-between mt-1">
            {errors.description ? (
              <div className="error-message">
                <AlertCircle className="w-4 h-4" />
                <span>{errors.description}</span>
              </div>
            ) : (
              <div className="text-sm text-gray-500">
                Be as specific as possible for an accurate estimate
              </div>
            )}
            <div className="text-sm text-gray-500">
              {description.length}/500
            </div>
          </div>
        </div>

        {/* Quantity/Volume */}
        <div>
          <label htmlFor="quantity" className="block text-sm font-medium text-gray-700 mb-2">
            Approximate Number of Items or Loads
          </label>
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={() => setQuantity(Math.max(1, parseInt(quantity || 1, 10) - 1))}
              disabled={isLoading || quantity <= 1}
              className="w-12 h-12 rounded-lg border-2 border-gray-300 hover:border-primary-500 hover:bg-primary-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-xl font-bold"
            >
              −
            </button>
            <input
              type="number"
              id="quantity"
              value={quantity}
              onChange={handleQuantityChange}
              min="1"
              max="100"
              disabled={isLoading}
              className="input-field text-center text-lg font-semibold w-24"
            />
            <button
              type="button"
              onClick={() => setQuantity(Math.min(100, parseInt(quantity || 1, 10) + 1))}
              disabled={isLoading || quantity >= 100}
              className="w-12 h-12 rounded-lg border-2 border-gray-300 hover:border-primary-500 hover:bg-primary-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-xl font-bold"
            >
              +
            </button>
          </div>
          {errors.quantity && (
            <div className="error-message mt-2">
              <AlertCircle className="w-4 h-4" />
              <span>{errors.quantity}</span>
            </div>
          )}
          <p className="text-sm text-gray-500 mt-2">
            💡 Not sure? That's okay! We'll give you a final quote on-site.
          </p>
        </div>

        {/* Info Box */}
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex gap-3">
            <div className="text-yellow-600 mt-0.5">⚠️</div>
            <div className="text-sm text-yellow-900">
              <p className="font-medium mb-1">Items We Cannot Accept</p>
              <p>
                Hazardous materials, chemicals, asbestos, medical waste, or anything illegal.
                Contact us if you're unsure about specific items.
              </p>
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
            disabled={isLoading}
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

export default Step3Items;
