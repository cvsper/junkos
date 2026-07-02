import React, { useState, useMemo } from 'react';
import { Package, AlertCircle, Loader, Search, ShoppingCart, Trash2, Plus, Minus } from 'lucide-react';

// ── Item catalog organized by category ─────────────────────────────────────
// Prices match backend CATEGORY_PRICES (~25% below 1-800-GOT-JUNK)
const ITEM_CATALOG = {
  furniture: {
    label: 'Furniture',
    icon: '\uD83D\uDECB\uFE0F',
    items: [
      { id: 'sofa',                label: 'Sofa / Couch',                price: 119 },
      { id: 'sofa_sleeper',        label: 'Sleeper Sofa',                price: 139 },
      { id: 'sofa_sectional',      label: 'Sectional Sofa',              price: 169 },
      { id: 'chair_recliner',      label: 'Recliner',                    price: 99 },
      { id: 'chair_office',        label: 'Office Chair',                price: 69 },
      { id: 'dresser',             label: 'Dresser',                     price: 99 },
      { id: 'bookcase',            label: 'Bookcase',                    price: 69 },
      { id: 'cabinet',             label: 'Cabinet / Armoire / Hutch',   price: 149 },
      { id: 'futon',               label: 'Futon',                       price: 79 },
      { id: 'filing_cabinet',      label: 'Filing Cabinet',              price: 69 },
      { id: 'desk_small',          label: 'Desk (Small)',                price: 69 },
      { id: 'desk_large',          label: 'Desk (Large)',                price: 99 },
    ],
  },
  tables: {
    label: 'Tables',
    icon: '\uD83E\uDE91',
    items: [
      { id: 'table_coffee',        label: 'Coffee Table',                price: 59 },
      { id: 'table_end',           label: 'End Table',                   price: 49 },
      { id: 'table_kitchen',       label: 'Kitchen Table',               price: 69 },
      { id: 'table_dining',        label: 'Dining Table',                price: 99 },
      { id: 'table_dining_chairs', label: 'Dining Table + Chairs',       price: 129 },
      { id: 'table_conference',    label: 'Conference Table',            price: 89 },
    ],
  },
  beds: {
    label: 'Beds & Mattresses',
    icon: '\uD83D\uDECF\uFE0F',
    items: [
      { id: 'mattress',            label: 'Mattress (any size)',         price: 99 },
      { id: 'box_spring',          label: 'Box Spring',                  price: 89 },
      { id: 'bed_frame',           label: 'Bed Frame / Headboard',      price: 75 },
      { id: 'bed_set',             label: 'Full Bed Set (frame + mattress + box spring)', price: 149 },
    ],
  },
  appliances: {
    label: 'Appliances',
    icon: '\uD83D\uDD0C',
    items: [
      { id: 'refrigerator',        label: 'Refrigerator (Standard)',     price: 129 },
      { id: 'refrigerator_bar',    label: 'Mini Fridge / Bar Fridge',    price: 69 },
      { id: 'washer',              label: 'Washer',                      price: 99 },
      { id: 'dryer',               label: 'Dryer',                       price: 99 },
      { id: 'washer_dryer_set',    label: 'Washer + Dryer Set',          price: 119 },
      { id: 'dishwasher',          label: 'Dishwasher',                  price: 69 },
      { id: 'stove',               label: 'Stove / Oven',               price: 79 },
      { id: 'microwave',           label: 'Microwave',                   price: 35 },
      { id: 'freezer_chest',       label: 'Freezer (Chest)',             price: 79 },
      { id: 'freezer_upright',     label: 'Freezer (Upright)',           price: 89 },
    ],
  },
  electronics: {
    label: 'Electronics',
    icon: '\uD83D\uDCFA',
    items: [
      { id: 'tv_flatscreen',       label: 'TV (Flat Screen)',            price: 89 },
      { id: 'tv_console',          label: 'TV (Console / CRT)',          price: 79 },
      { id: 'tv_stand',            label: 'TV Stand',                    price: 59 },
      { id: 'entertainment_center',label: 'Entertainment Center',        price: 89 },
      { id: 'computer',            label: 'Computer / Monitor',          price: 59 },
      { id: 'copier_commercial',   label: 'Copier / Printer (Commercial)', price: 109 },
      { id: 'printer',             label: 'Printer (Home)',              price: 35 },
    ],
  },
  exercise: {
    label: 'Exercise',
    icon: '\uD83C\uDFCB\uFE0F',
    items: [
      { id: 'treadmill',           label: 'Treadmill',                   price: 89 },
      { id: 'elliptical',          label: 'Elliptical',                  price: 99 },
      { id: 'bike_stationary',     label: 'Stationary Bike',             price: 69 },
    ],
  },
  outdoor: {
    label: 'Outdoor & Specialty',
    icon: '\uD83C\uDFE1',
    items: [
      { id: 'bbq_grill',           label: 'BBQ Grill',                   price: 69 },
      { id: 'basketball_hoop',     label: 'Basketball Hoop',             price: 79 },
      { id: 'basketball_hoop_stand', label: 'Basketball Hoop + Stand',   price: 99 },
      { id: 'lawn_mower_push',     label: 'Lawn Mower (Push)',           price: 69 },
      { id: 'lawn_mower_riding',   label: 'Lawn Mower (Riding)',         price: 149 },
      { id: 'hot_tub',             label: 'Hot Tub',                     price: 349 },
      { id: 'pool_table',          label: 'Pool Table',                  price: 269 },
      { id: 'piano',               label: 'Piano',                       price: 299 },
      { id: 'bike',                label: 'Bicycle',                     price: 49 },
    ],
  },
  general: {
    label: 'General / Bulk',
    icon: '\uD83D\uDCE6',
    items: [
      { id: 'general',             label: 'General Junk (per item)',     price: 25 },
      { id: 'yard_waste',          label: 'Yard Waste (per cubic yard)', price: 30 },
      { id: 'construction',        label: 'Construction Debris (per cubic yard)', price: 45 },
      { id: 'other',               label: 'Other',                       price: 25 },
    ],
  },
};

// ── Truck load pricing (matches backend TRUCK_LOAD_PRICES) ─────────────────
const TRUCK_LOAD_OPTIONS = [
  { id: 'min',  label: 'Minimum Load',   price: 119, desc: 'A few small items' },
  { id: '1/8',  label: '1/8 Truck',      price: 179, desc: '~2 ft in the truck' },
  { id: '1/4',  label: '1/4 Truck',      price: 279, desc: '~4 ft in the truck' },
  { id: '1/3',  label: '1/3 Truck',      price: 329, desc: '~5 ft in the truck' },
  { id: '1/2',  label: '1/2 Truck',      price: 389, desc: '~6 ft in the truck' },
  { id: '2/3',  label: '2/3 Truck',      price: 449, desc: '~8 ft in the truck' },
  { id: '3/4',  label: '3/4 Truck',      price: 489, desc: '~9 ft in the truck' },
  { id: 'full', label: 'Full Truck',     price: 579, desc: '10 ft — whole truck' },
];

// ── Recycling fees (auto-applied for certain items) ────────────────────────
const RECYCLING_FEE_MAP = {
  mattress:         { label: 'Mattress recycling',   fee: 20 },
  box_spring:       { label: 'Box spring recycling', fee: 20 },
  refrigerator:     { label: 'Freon recovery',       fee: 10 },
  freezer_chest:    { label: 'Freon recovery',       fee: 10 },
  freezer_upright:  { label: 'Freon recovery',       fee: 10 },
  tv_console:       { label: 'CRT disposal',         fee: 10 },
  washer:           { label: 'Freon recovery',       fee: 10 },
  dryer:            { label: 'Freon recovery',       fee: 10 },
  washer_dryer_set: { label: 'Freon recovery',       fee: 10 },
  dishwasher:       { label: 'Freon recovery',       fee: 10 },
};

// Flat lookup for item info by id
const ITEM_LOOKUP = {};
Object.values(ITEM_CATALOG).forEach((cat) => {
  cat.items.forEach((item) => {
    ITEM_LOOKUP[item.id] = item;
  });
});

const Step3Items = ({ formData, updateFormData, nextStep, prevStep, setError, setIsLoading, isLoading }) => {
  // "items" = pick specific items, "load" = estimate by truck volume
  const [pricingMode, setPricingMode] = useState(formData.pricingMode || 'items');
  const [selectedLoad, setSelectedLoad] = useState(formData.selectedLoad || null);

  // cart: { [itemId]: quantity }
  const [cart, setCart] = useState(() => {
    if (formData.selectedItems && typeof formData.selectedItems === 'object') {
      return { ...formData.selectedItems };
    }
    return {};
  });
  const [activeCategory, setActiveCategory] = useState('furniture');
  const [searchQuery, setSearchQuery] = useState('');
  const [notes, setNotes] = useState(formData.itemDescription || '');

  const addItem = (itemId) => {
    setCart((prev) => ({ ...prev, [itemId]: (prev[itemId] || 0) + 1 }));
  };

  const removeItem = (itemId) => {
    setCart((prev) => {
      const updated = { ...prev };
      if (updated[itemId] > 1) {
        updated[itemId] -= 1;
      } else {
        delete updated[itemId];
      }
      return updated;
    });
  };

  const clearItem = (itemId) => {
    setCart((prev) => {
      const updated = { ...prev };
      delete updated[itemId];
      return updated;
    });
  };

  const cartItems = useMemo(() => {
    return Object.entries(cart)
      .filter(([, qty]) => qty > 0)
      .map(([id, qty]) => ({
        id,
        ...ITEM_LOOKUP[id],
        quantity: qty,
        lineTotal: (ITEM_LOOKUP[id]?.price || 0) * qty,
      }));
  }, [cart]);

  const totalItems = cartItems.reduce((sum, i) => sum + i.quantity, 0);
  const subtotal = cartItems.reduce((sum, i) => sum + i.lineTotal, 0);

  // Calculate recycling fees
  const recyclingFees = useMemo(() => {
    const fees = [];
    cartItems.forEach((item) => {
      const feeInfo = RECYCLING_FEE_MAP[item.id];
      if (feeInfo) {
        fees.push({
          itemId: item.id,
          label: feeInfo.label,
          unitFee: feeInfo.fee,
          quantity: item.quantity,
          total: feeInfo.fee * item.quantity,
        });
      }
    });
    return fees;
  }, [cartItems]);

  const recyclingTotal = recyclingFees.reduce((sum, f) => sum + f.total, 0);

  // Search filter
  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) return null;
    const q = searchQuery.toLowerCase();
    const results = [];
    Object.values(ITEM_CATALOG).forEach((cat) => {
      cat.items.forEach((item) => {
        if (item.label.toLowerCase().includes(q)) {
          results.push(item);
        }
      });
    });
    return results;
  }, [searchQuery]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (pricingMode === 'items' && totalItems === 0) {
      setError('Please add at least one item');
      return;
    }
    if (pricingMode === 'load' && !selectedLoad) {
      setError('Please select a truck load size');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      updateFormData('pricingMode', pricingMode);
      updateFormData('itemDescription', notes);

      if (pricingMode === 'items') {
        const items = cartItems.map((item) => ({
          category: item.id,
          quantity: item.quantity,
        }));
        updateFormData('selectedItems', cart);
        updateFormData('items', items);
        updateFormData('quantity', totalItems);
        updateFormData('itemCategory', cartItems.length === 1 ? cartItems[0].id : 'mixed');
        updateFormData('selectedLoad', null);
      } else {
        const loadOption = TRUCK_LOAD_OPTIONS.find((o) => o.id === selectedLoad);
        updateFormData('selectedLoad', selectedLoad);
        updateFormData('loadPrice', loadOption?.price || 0);
        updateFormData('selectedItems', {});
        updateFormData('items', []);
        updateFormData('quantity', 1);
        updateFormData('itemCategory', 'truck_load');
      }

      nextStep();
    } catch (err) {
      setError('Failed to save item details. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const categoryKeys = Object.keys(ITEM_CATALOG);
  const displayItems = filteredItems || ITEM_CATALOG[activeCategory]?.items || [];

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
          Select items below. Our prices are up to 40% less than the big guys.
        </p>

        {/* Donation-first promise */}
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex gap-3">
          <span className="text-green-600 text-lg mt-0.5">&#9851;&#65039;</span>
          <div className="text-sm text-green-900">
            <p className="font-semibold">Donate First, Dispose Last</p>
            <p className="text-green-800 mt-0.5">
              We partner with local charities and shelters. Usable items are donated before
              anything goes to the landfill. You'll receive a donation receipt for tax purposes
              when applicable.
            </p>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Pricing Mode Toggle */}
        <div className="flex rounded-lg border-2 border-gray-200 overflow-hidden">
          <button
            type="button"
            onClick={() => setPricingMode('items')}
            className={`flex-1 py-3 text-sm font-semibold transition-all ${
              pricingMode === 'items'
                ? 'bg-red-600 text-white'
                : 'bg-white text-gray-600 hover:bg-gray-50'
            }`}
          >
            Pick Specific Items
          </button>
          <button
            type="button"
            onClick={() => setPricingMode('load')}
            className={`flex-1 py-3 text-sm font-semibold transition-all ${
              pricingMode === 'load'
                ? 'bg-red-600 text-white'
                : 'bg-white text-gray-600 hover:bg-gray-50'
            }`}
          >
            Estimate by Truck Load
          </button>
        </div>

        {/* ── TRUCK LOAD MODE ────────────────────────────────────── */}
        {pricingMode === 'load' && (
          <div className="space-y-3">
            <p className="text-sm text-gray-600">
              Not sure exactly what you have? Just estimate how much of the truck you'll fill.
              Our truck is 10 ft long x 8 ft wide x 5 ft high.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {TRUCK_LOAD_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setSelectedLoad(opt.id)}
                  className={`p-4 rounded-lg border-2 text-left transition-all ${
                    selectedLoad === opt.id
                      ? 'border-red-400 bg-red-50'
                      : 'border-gray-200 bg-white hover:border-gray-300'
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="font-semibold text-gray-900">{opt.label}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{opt.desc}</p>
                    </div>
                    <span className="text-lg font-bold text-red-600">${opt.price}</span>
                  </div>
                </button>
              ))}
            </div>
            {selectedLoad && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
                Selected: <strong>{TRUCK_LOAD_OPTIONS.find((o) => o.id === selectedLoad)?.label}</strong>
                {' '}&mdash; <strong>${TRUCK_LOAD_OPTIONS.find((o) => o.id === selectedLoad)?.price}</strong>
                {' '}+ service fee. Final price confirmed on-site.
              </div>
            )}
          </div>
        )}

        {/* ── ITEM PICKER MODE ───────────────────────────────────── */}
        {pricingMode === 'items' && (
          <>
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search items (e.g. sofa, refrigerator, mattress)..."
            className="input-field pl-10"
          />
        </div>

        {/* Category Tabs (hidden during search) */}
        {!filteredItems && (
          <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1 scrollbar-hide">
            {categoryKeys.map((key) => {
              const cat = ITEM_CATALOG[key];
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setActiveCategory(key)}
                  className={`flex-shrink-0 px-3 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
                    activeCategory === key
                      ? 'bg-red-600 text-white shadow-sm'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  <span className="mr-1.5">{cat.icon}</span>
                  {cat.label}
                </button>
              );
            })}
          </div>
        )}

        {/* Item Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {displayItems.map((item) => {
            const qty = cart[item.id] || 0;
            return (
              <div
                key={item.id}
                className={`flex items-center justify-between p-3 rounded-lg border-2 transition-all ${
                  qty > 0
                    ? 'border-red-400 bg-red-50'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                }`}
              >
                <div className="flex-1 min-w-0 mr-3">
                  <p className="text-sm font-medium text-gray-900 truncate">{item.label}</p>
                  <p className="text-sm font-semibold text-red-600">${item.price}</p>
                </div>

                {qty === 0 ? (
                  <button
                    type="button"
                    onClick={() => addItem(item.id)}
                    disabled={isLoading}
                    className="flex-shrink-0 w-9 h-9 rounded-lg bg-red-600 text-white flex items-center justify-center hover:bg-red-700 transition-colors"
                  >
                    <Plus className="w-5 h-5" />
                  </button>
                ) : (
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <button
                      type="button"
                      onClick={() => removeItem(item.id)}
                      className="w-8 h-8 rounded-lg border-2 border-gray-300 text-gray-600 flex items-center justify-center hover:bg-gray-100 transition-colors"
                    >
                      <Minus className="w-4 h-4" />
                    </button>
                    <span className="w-7 text-center font-semibold text-gray-900">{qty}</span>
                    <button
                      type="button"
                      onClick={() => addItem(item.id)}
                      className="w-8 h-8 rounded-lg bg-red-600 text-white flex items-center justify-center hover:bg-red-700 transition-colors"
                    >
                      <Plus className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {filteredItems && filteredItems.length === 0 && (
          <p className="text-center text-gray-500 py-4">
            No items match "{searchQuery}". Try a different search or browse categories above.
          </p>
        )}

        {/* Cart Summary */}
        {cartItems.length > 0 && (
          <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
            <div className="flex items-center gap-2 mb-3">
              <ShoppingCart className="w-5 h-5 text-gray-700" />
              <h3 className="font-semibold text-gray-900">
                Your Items ({totalItems})
              </h3>
            </div>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {cartItems.map((item) => (
                <div key={item.id} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <button
                      type="button"
                      onClick={() => clearItem(item.id)}
                      className="text-gray-400 hover:text-red-500 transition-colors flex-shrink-0"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                    <span className="text-gray-700 truncate">{item.label}</span>
                    {item.quantity > 1 && (
                      <span className="text-gray-400 flex-shrink-0">x{item.quantity}</span>
                    )}
                  </div>
                  <span className="font-medium text-gray-900 flex-shrink-0 ml-2">
                    ${item.lineTotal}
                  </span>
                </div>
              ))}
            </div>
            {/* Recycling fees */}
            {recyclingFees.length > 0 && (
              <div className="border-t border-gray-200 mt-2 pt-2 space-y-1">
                {recyclingFees.map((f, idx) => (
                  <div key={idx} className="flex justify-between text-xs text-gray-500">
                    <span>{f.label}{f.quantity > 1 ? ` x${f.quantity}` : ''}</span>
                    <span>+${f.total}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="border-t border-gray-300 mt-3 pt-3">
              <div className="flex justify-between">
                <span className="font-semibold text-gray-900">Items</span>
                <span className="font-semibold text-gray-900">${subtotal}</span>
              </div>
              {recyclingTotal > 0 && (
                <div className="flex justify-between text-sm text-gray-600 mt-1">
                  <span>Disposal/recycling fees</span>
                  <span>${recyclingTotal}</span>
                </div>
              )}
              <div className="flex justify-between mt-2">
                <span className="font-bold text-gray-900">Estimated Subtotal</span>
                <span className="font-bold text-red-600 text-lg">${subtotal + recyclingTotal}</span>
              </div>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              + service fee. Final price confirmed on-site.
            </p>
          </div>
        )}
          </>
        )}

        {/* Additional Notes */}
        <div>
          <label htmlFor="notes" className="block text-sm font-medium text-gray-700 mb-2">
            Additional Notes (optional)
          </label>
          <textarea
            id="notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Anything else we should know? (e.g. stairs, narrow hallways, item location...)"
            rows={3}
            maxLength={500}
            disabled={isLoading}
            className="input-field resize-none"
          />
        </div>

        {/* Items We Cannot Accept */}
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex gap-3">
            <div className="text-yellow-600 mt-0.5">&#9888;&#65039;</div>
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
            &larr; Back
          </button>
          <button
            type="submit"
            disabled={isLoading || (pricingMode === 'items' && totalItems === 0) || (pricingMode === 'load' && !selectedLoad)}
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
                <span>&rarr;</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default Step3Items;
