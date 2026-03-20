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
      // Build v2-format request with items array
      const scheduledDate = formData.selectedDate
        ? (typeof formData.selectedDate === 'string' ? formData.selectedDate : format(formData.selectedDate, 'yyyy-MM-dd'))
        : undefined;

      let result;

      if (formData.pricingMode === 'load' && formData.selectedLoad) {
        // Truck load pricing mode
        result = await api.getLoadEstimate({
          load_size: formData.selectedLoad,
          scheduledDate,
        });
      } else {
        // Item-based pricing mode
        const estimateData = {
          items: formData.items || [{ category: formData.itemCategory, quantity: formData.quantity || 1 }],
          address: typeof formData.address === 'object'
            ? formData.address
            : { street: formData.address },
          scheduledDate,
        };
        result = await api.getPriceEstimate(estimateData);
      }

      setEstimate(result.estimate);
      updateFormData('estimate', result.estimate);
    } catch (err) {
      // Fallback: calculate from local data
      let fallbackEstimate;

      if (formData.pricingMode === 'load' && formData.loadPrice) {
        const basePrice = formData.loadPrice;
        const serviceFee = Math.round(basePrice * 0.08 * 100) / 100;
        fallbackEstimate = {
          load_size: formData.selectedLoad,
          base_price: basePrice,
          service_fee: serviceFee,
          recycling_fees: 0,
          labor_fee: 0,
          total: Math.max(basePrice + serviceFee, 79),
          surge_amount: 0,
          surge_reasons: [],
          is_load_estimate: true,
        };
      } else {
        const items = formData.items || [];
        let subtotal = 0;
        items.forEach((item) => {
          subtotal += (item.price || 79) * (item.quantity || 1);
        });
        if (subtotal === 0) subtotal = 150;

        const serviceFee = Math.round(subtotal * 0.08 * 100) / 100;
        const total = Math.max(subtotal + serviceFee, 79);
        const totalQty = items.reduce((s, i) => s + (i.quantity || 1), 0);

        fallbackEstimate = {
          items_subtotal: subtotal,
          items: items.map((i) => ({
            category: i.category,
            quantity: i.quantity || 1,
            unit_price: i.price || 79,
            line_total: (i.price || 79) * (i.quantity || 1),
          })),
          service_fee: serviceFee,
          total: total,
          estimated_duration: 30 + totalQty * 8,
          truck_size: totalQty <= 5 ? 'Standard Pickup' : totalQty <= 12 ? 'Large Truck' : 'Extra-Large Truck',
          volume_discount: 0,
          surge_amount: 0,
          surge_reasons: [],
          recycling_fees: 0,
          total_quantity: totalQty,
          subtotal: subtotal,
          serviceFee: serviceFee,
          tax: 0,
          estimatedDuration: `${30 + totalQty * 8} min`,
          truckSize: totalQty <= 5 ? 'Standard Pickup' : totalQty <= 12 ? 'Large Truck' : 'Extra-Large Truck',
        };
      }

      setEstimate(fallbackEstimate);
      updateFormData('estimate', fallbackEstimate);

      console.error('Failed to fetch estimate from API, using fallback:', err);
    } finally {
      setLoadingEstimate(false);
    }
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

  // Normalize estimate keys (backend uses snake_case, fallback uses camelCase)
  const isLoadEstimate = estimate?.is_load_estimate || estimate?.load_size;
  const loadSize = estimate?.load_size;
  const basePrice = estimate?.base_price ?? 0;
  const itemsSubtotal = estimate?.items_subtotal ?? estimate?.subtotal ?? basePrice ?? 0;
  const serviceFee = estimate?.service_fee ?? estimate?.serviceFee ?? 0;
  const total = estimate?.total ?? 0;
  const volumeDiscount = estimate?.volume_discount ?? 0;
  const surgeAmount = estimate?.surge_amount ?? 0;
  const surgeReasons = estimate?.surge_reasons ?? [];
  const itemBreakdown = estimate?.items ?? [];
  const recyclingFees = estimate?.recycling_fees ?? 0;
  const recyclingBreakdown = estimate?.recycling_breakdown ?? [];
  const laborFee = estimate?.labor_fee ?? 0;
  const laborRate = estimate?.labor_fee_rate ?? 55;
  const estimatedDuration = estimate?.estimated_duration ?? estimate?.estimatedDuration;
  const truckSize = estimate?.truck_size ?? estimate?.truckSize;

  const durationLabel = typeof estimatedDuration === 'number'
    ? estimatedDuration < 60
      ? `${estimatedDuration} min`
      : `${Math.round(estimatedDuration / 60 * 10) / 10} hours`
    : estimatedDuration;

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
          Based on the items you selected, here's your estimated cost.
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
              <p className="text-sm text-gray-600">
                {typeof formData.address === 'object'
                  ? formData.address.street || formData.address.formatted || JSON.stringify(formData.address)
                  : formData.address}
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <Calendar className="w-5 h-5 text-gray-400 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-700">Scheduled For</p>
              <p className="text-sm text-gray-600">
                {formData.selectedDate
                  ? format(
                      typeof formData.selectedDate === 'string'
                        ? new Date(formData.selectedDate)
                        : formData.selectedDate,
                      'EEEE, MMMM d, yyyy'
                    )
                  : 'TBD'}{' '}
                at {TIME_SLOTS.find((slot) => slot.value === formData.selectedTime)?.label || formData.selectedTime}
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <Package className="w-5 h-5 text-gray-400 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-700">Items</p>
              <p className="text-sm text-gray-600">
                {estimate?.total_quantity || formData.quantity || 0} item(s)
              </p>
              {formData.itemDescription && (
                <p className="text-xs text-gray-500 mt-1">
                  Note: {formData.itemDescription.substring(0, 100)}
                  {formData.itemDescription.length > 100 ? '...' : ''}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Price Breakdown */}
        {estimate && (
          <div className="border-2 border-primary-200 rounded-lg p-5">
            <h3 className="font-semibold text-gray-900 mb-4">Price Breakdown</h3>

            <div className="space-y-2">
              {/* Truck load line (load mode) */}
              {isLoadEstimate && (
                <div className="flex justify-between text-gray-700 pb-2 border-b border-gray-200">
                  <span className="capitalize">{loadSize} truck load</span>
                  <span>{formatCurrency(basePrice)}</span>
                </div>
              )}

              {/* Per-item lines (item mode) */}
              {!isLoadEstimate && itemBreakdown.length > 0 && (
                <div className="space-y-1.5 pb-3 border-b border-gray-200">
                  {itemBreakdown.map((item, idx) => (
                    <div key={idx} className="flex justify-between text-sm text-gray-600">
                      <span className="capitalize">
                        {(item.category || '').replace(/_/g, ' ')}
                        {item.quantity > 1 ? ` x${item.quantity}` : ''}
                      </span>
                      <span>{formatCurrency(item.line_total)}</span>
                    </div>
                  ))}
                </div>
              )}

              {!isLoadEstimate && (
                <div className="flex justify-between text-gray-700">
                  <span>Items Subtotal</span>
                  <span>{formatCurrency(itemsSubtotal)}</span>
                </div>
              )}

              {volumeDiscount > 0 && (
                <div className="flex justify-between text-green-600">
                  <span>Volume Discount</span>
                  <span>-{formatCurrency(volumeDiscount)}</span>
                </div>
              )}

              {surgeAmount > 0 && (
                <div className="flex justify-between text-orange-600">
                  <span>
                    {surgeReasons.length > 0 ? surgeReasons.join(', ') : 'Surge'}
                  </span>
                  <span>+{formatCurrency(surgeAmount)}</span>
                </div>
              )}

              {/* Recycling / disposal fees */}
              {recyclingFees > 0 && (
                <div>
                  <div className="flex justify-between text-gray-700">
                    <span>Disposal &amp; Recycling Fees</span>
                    <span>{formatCurrency(recyclingFees)}</span>
                  </div>
                  {recyclingBreakdown.length > 0 && (
                    <div className="ml-4 space-y-0.5 mt-1">
                      {recyclingBreakdown.map((fee, idx) => (
                        <div key={idx} className="flex justify-between text-xs text-gray-500">
                          <span className="capitalize">{(fee.fee_type || '').replace(/_/g, ' ')}{fee.quantity > 1 ? ` x${fee.quantity}` : ''}</span>
                          <span>{formatCurrency(fee.total)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Labor fee */}
              {laborFee > 0 && (
                <div className="flex justify-between text-gray-700">
                  <span>Labor ({estimate?.labor_hours}hr x ${laborRate}/hr)</span>
                  <span>{formatCurrency(laborFee)}</span>
                </div>
              )}

              {serviceFee > 0 && (
                <div className="flex justify-between text-gray-700">
                  <span>Service Fee</span>
                  <span>{formatCurrency(serviceFee)}</span>
                </div>
              )}

              <div className="border-t-2 border-gray-300 pt-3 mt-3">
                <div className="flex justify-between items-center">
                  <span className="text-xl font-bold text-gray-900">Total</span>
                  <span className="text-2xl font-bold text-primary-600">
                    {formatCurrency(total)}
                  </span>
                </div>
              </div>

              <div className="flex justify-between text-sm text-gray-600 pt-2">
                <span>Estimated Duration</span>
                <span className="font-medium">{durationLabel}</span>
              </div>

              {truckSize && (
                <div className="flex justify-between text-sm text-gray-600">
                  <span>Truck Size</span>
                  <span className="font-medium">{truckSize}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Donation Promise */}
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex gap-3">
            <span className="text-green-600 text-lg mt-0.5">&#9851;&#65039;</span>
            <div className="text-sm text-green-900">
              <p className="font-semibold">Donate First, Dispose Last</p>
              <p className="text-green-800 mt-1">
                Usable items are donated to local charities and shelters before anything
                goes to the landfill. You'll receive a donation receipt for tax purposes
                when applicable. Recycling and responsible disposal for everything else.
              </p>
            </div>
          </div>
        </div>

        {/* Important Notes */}
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex gap-3">
            <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5" />
            <div className="text-sm text-yellow-900">
              <p className="font-medium mb-2">Please Note:</p>
              <ul className="list-disc list-inside space-y-1 text-yellow-800">
                <li>This is an <strong>estimate</strong> based on your selections</li>
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
            &larr; Back
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
                <span>&rarr;</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default Step5Estimate;
