// Form validation utilities

export const validateAddress = (address) => {
  if (!address || address.trim().length === 0) {
    return 'Address is required';
  }
  if (address.length < 10) {
    return 'Please enter a complete address';
  }
  return null;
};

export const validatePhotos = (photos) => {
  if (!photos || photos.length === 0) {
    return 'Please upload at least one photo';
  }
  if (photos.length > 10) {
    return 'Maximum 10 photos allowed';
  }
  
  // Check file sizes (max 10MB per file)
  const maxSize = 10 * 1024 * 1024;
  for (const photo of photos) {
    if (photo.size > maxSize) {
      return 'Each photo must be less than 10MB';
    }
  }
  
  // Check file types
  const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
  for (const photo of photos) {
    if (!allowedTypes.includes(photo.type)) {
      return 'Only JPG, PNG, and WebP images are allowed';
    }
  }
  
  return null;
};

export const validateItemDescription = (description) => {
  if (!description || description.trim().length === 0) {
    return 'Item description is required';
  }
  if (description.length < 10) {
    return 'Please provide more details (at least 10 characters)';
  }
  if (description.length > 500) {
    return 'Description is too long (max 500 characters)';
  }
  return null;
};

export const validateQuantity = (quantity) => {
  if (!quantity || isNaN(quantity)) {
    return 'Quantity is required';
  }
  const num = parseInt(quantity, 10);
  if (num < 1) {
    return 'Quantity must be at least 1';
  }
  if (num > 100) {
    return 'Quantity seems too high. Please contact us directly.';
  }
  return null;
};

export const validateDateTime = (date, time) => {
  if (!date) {
    return 'Please select a date';
  }
  if (!time) {
    return 'Please select a time';
  }
  
  const selectedDateTime = new Date(date);
  selectedDateTime.setHours(parseInt(time.split(':')[0]), parseInt(time.split(':')[1]));
  
  const now = new Date();
  const minBookingTime = new Date(now.getTime() + 24 * 60 * 60 * 1000); // 24 hours from now
  
  if (selectedDateTime < minBookingTime) {
    return 'Booking must be at least 24 hours in advance';
  }
  
  return null;
};

export const validateEmail = (email) => {
  if (!email || email.trim().length === 0) {
    return 'Email is required';
  }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    return 'Please enter a valid email address';
  }
  return null;
};

export const validatePhone = (phone) => {
  if (!phone || phone.trim().length === 0) {
    return 'Phone number is required';
  }
  // Remove all non-digit characters
  const digits = phone.replace(/\D/g, '');
  if (digits.length < 10) {
    return 'Please enter a valid phone number';
  }
  return null;
};

export const formatPhoneNumber = (value) => {
  if (!value) return value;
  const phoneNumber = value.replace(/[^\d]/g, '');
  const phoneNumberLength = phoneNumber.length;
  
  if (phoneNumberLength < 4) return phoneNumber;
  if (phoneNumberLength < 7) {
    return `(${phoneNumber.slice(0, 3)}) ${phoneNumber.slice(3)}`;
  }
  return `(${phoneNumber.slice(0, 3)}) ${phoneNumber.slice(3, 6)}-${phoneNumber.slice(6, 10)}`;
};

export const formatCurrency = (amount) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
};
