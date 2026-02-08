import { 
  View, 
  Text, 
  Pressable, 
  ScrollView, 
  StyleSheet, 
  TextInput, 
  Alert,
  Animated,
  Dimensions,
  ActivityIndicator,
  Image,
  Platform
} from 'react-native';
import { useState, useRef, useEffect } from 'react';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

// Design System Colors
const COLORS = {
  primary: '#6366F1',
  secondary: '#818CF8',
  cta: '#10B981',
  background: '#F5F3FF',
  text: '#1E1B4B',
  muted: '#64748B',
  border: '#E2E8F0',
  white: '#FFFFFF',
  success: '#10B981',
  error: '#EF4444',
};

export default function App() {
  const [screen, setScreen] = useState<'welcome' | 'address' | 'photos' | 'service' | 'datetime' | 'confirmation'>('welcome');
  const [bookingData, setBookingData] = useState({
    address: '',
    city: '',
    state: '',
    zip: '',
    photos: [] as string[],
    serviceType: '',
    serviceDetails: '',
    date: '',
    time: '',
  });

  const updateBookingData = (data: Partial<typeof bookingData>) => {
    setBookingData(prev => ({ ...prev, ...data }));
  };

  const screens = {
    welcome: <WelcomeScreen onNext={() => setScreen('address')} />,
    address: <AddressScreen data={bookingData} onUpdate={updateBookingData} onNext={() => setScreen('photos')} onBack={() => setScreen('welcome')} />,
    photos: <PhotoScreen data={bookingData} onUpdate={updateBookingData} onNext={() => setScreen('service')} onBack={() => setScreen('address')} />,
    service: <ServiceScreen data={bookingData} onUpdate={updateBookingData} onNext={() => setScreen('datetime')} onBack={() => setScreen('photos')} />,
    datetime: <DateTimeScreen data={bookingData} onUpdate={updateBookingData} onNext={() => setScreen('confirmation')} onBack={() => setScreen('service')} />,
    confirmation: <ConfirmationScreen data={bookingData} onConfirm={() => {
      Alert.alert('Success! 🎉', 'Your booking has been confirmed. We\'ll see you soon!', [
        { text: 'Done', onPress: () => setScreen('welcome') }
      ]);
    }} onBack={() => setScreen('datetime')} />,
  };

  return screens[screen];
}

// ============= WELCOME SCREEN =============
function WelcomeScreen({ onNext }: { onNext: () => void }) {
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 600,
      useNativeDriver: true,
    }).start();
  }, []);

  return (
    <View style={styles.container}>
      <ScrollView 
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <Animated.View style={[styles.welcomeHero, { opacity: fadeAnim }]}>
          {/* Logo Placeholder */}
          <View style={styles.logoPlaceholder}>
            <Text style={styles.logoText}>🚛</Text>
          </View>
          
          <Text style={styles.welcomeTitle}>JunkOS</Text>
          
          <View style={styles.gradientBadge}>
            <Text style={styles.tagline}>Book junk removal in 3 taps</Text>
          </View>

          {/* Social Proof */}
          <View style={styles.socialProof}>
            <View style={styles.proofItem}>
              <Text style={styles.proofIcon}>⭐</Text>
              <Text style={styles.proofValue}>4.9/5</Text>
            </View>
            <View style={styles.proofDivider} />
            <View style={styles.proofItem}>
              <Text style={styles.proofIcon}>✓</Text>
              <Text style={styles.proofValue}>2,500+ jobs</Text>
            </View>
            <View style={styles.proofDivider} />
            <View style={styles.proofItem}>
              <Text style={styles.proofIcon}>🔒</Text>
              <Text style={styles.proofValue}>Insured</Text>
            </View>
          </View>

          <Pressable 
            style={({ pressed }) => [
              styles.primaryCTA,
              pressed && styles.buttonPressed
            ]}
            onPress={onNext}
          >
            <Text style={styles.primaryCTAText}>Get Started →</Text>
          </Pressable>
        </Animated.View>

        {/* Features */}
        <View style={styles.featuresSection}>
          <Text style={styles.sectionTitle}>How it works</Text>
          
          <FeatureCard 
            icon="📍"
            title="Tell us where"
            description="Enter your pickup location"
            step={1}
          />
          <FeatureCard 
            icon="📸"
            title="Show us what"
            description="Snap photos of items to haul"
            step={2}
          />
          <FeatureCard 
            icon="📅"
            title="Pick a time"
            description="Choose when we come by"
            step={3}
          />
          <FeatureCard 
            icon="✨"
            title="We handle it"
            description="Sit back and relax!"
            step={4}
          />
        </View>

        {/* Trust Badge */}
        <View style={styles.trustSection}>
          <Text style={styles.trustText}>
            Trusted by 500+ customers • Same-day pickup • Eco-friendly
          </Text>
        </View>
      </ScrollView>
    </View>
  );
}

function FeatureCard({ icon, title, description, step }: any) {
  return (
    <View style={styles.featureCard}>
      <View style={styles.featureIconContainer}>
        <Text style={styles.featureIcon}>{icon}</Text>
      </View>
      <View style={styles.featureContent}>
        <View style={styles.featureHeader}>
          <Text style={styles.featureTitle}>{title}</Text>
          <View style={styles.stepBadge}>
            <Text style={styles.stepBadgeText}>{step}</Text>
          </View>
        </View>
        <Text style={styles.featureDescription}>{description}</Text>
      </View>
    </View>
  );
}

// ============= ADDRESS SCREEN =============
function AddressScreen({ data, onUpdate, onNext, onBack }: any) {
  const [errors, setErrors] = useState<any>({});

  const validate = () => {
    const newErrors: any = {};
    if (!data.address) newErrors.address = true;
    if (!data.city) newErrors.city = true;
    if (!data.state) newErrors.state = true;
    if (!data.zip) newErrors.zip = true;
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (validate()) {
      onNext();
    } else {
      Alert.alert('Missing info', 'Please fill in all address fields');
    }
  };

  return (
    <View style={styles.container}>
      <ScreenHeader 
        title="Pickup Location"
        subtitle="Where should we come?"
        onBack={onBack}
        step={1}
        totalSteps={5}
      />
      
      <ScrollView 
        contentContainerStyle={styles.formScrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Map Placeholder */}
        <View style={styles.mapPlaceholder}>
          <Text style={styles.mapIcon}>📍</Text>
          <Text style={styles.mapText}>Map Preview</Text>
          <Pressable style={styles.locationButton}>
            <Text style={styles.locationButtonText}>📍 Use Current Location</Text>
          </Pressable>
        </View>

        <View style={styles.formSection}>
          <InputField
            label="Street Address"
            value={data.address}
            onChangeText={(text: string) => onUpdate({ address: text })}
            placeholder="123 Main Street"
            error={errors.address}
            icon="🏠"
          />

          <InputField
            label="City"
            value={data.city}
            onChangeText={(text: string) => onUpdate({ city: text })}
            placeholder="San Francisco"
            error={errors.city}
            icon="🌆"
          />

          <View style={styles.row}>
            <View style={{ flex: 1, marginRight: 8 }}>
              <InputField
                label="State"
                value={data.state}
                onChangeText={(text: string) => onUpdate({ state: text })}
                placeholder="CA"
                error={errors.state}
                maxLength={2}
              />
            </View>
            <View style={{ flex: 1, marginLeft: 8 }}>
              <InputField
                label="ZIP Code"
                value={data.zip}
                onChangeText={(text: string) => onUpdate({ zip: text })}
                placeholder="94105"
                error={errors.zip}
                keyboardType="number-pad"
                maxLength={5}
              />
            </View>
          </View>
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <Pressable 
          style={({ pressed }) => [
            styles.primaryButton,
            pressed && styles.buttonPressed
          ]}
          onPress={handleNext}
        >
          <Text style={styles.primaryButtonText}>Continue →</Text>
        </Pressable>
      </View>
    </View>
  );
}

// ============= PHOTO SCREEN =============
function PhotoScreen({ data, onUpdate, onNext, onBack }: any) {
  const [loading, setLoading] = useState(false);

  const addPhoto = () => {
    // Simulate adding photo
    const newPhotos = [...data.photos, `photo-${Date.now()}`];
    onUpdate({ photos: newPhotos });
  };

  const removePhoto = (index: number) => {
    const newPhotos = data.photos.filter((_: any, i: number) => i !== index);
    onUpdate({ photos: newPhotos });
  };

  return (
    <View style={styles.container}>
      <ScreenHeader 
        title="Upload Photos"
        subtitle="Show us what needs to go"
        onBack={onBack}
        step={2}
        totalSteps={5}
      />
      
      <ScrollView 
        contentContainerStyle={styles.formScrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Empty State */}
        {data.photos.length === 0 && (
          <View style={styles.emptyState}>
            <Text style={styles.emptyStateIcon}>📸</Text>
            <Text style={styles.emptyStateTitle}>No photos yet</Text>
            <Text style={styles.emptyStateText}>
              Take photos of the items you want removed
            </Text>
          </View>
        )}

        {/* Photo Grid */}
        {data.photos.length > 0 && (
          <View style={styles.photoGrid}>
            {data.photos.map((photo: string, index: number) => (
              <View key={photo} style={styles.photoThumbnail}>
                <View style={styles.photoPlaceholder}>
                  <Text style={styles.photoPlaceholderText}>📷</Text>
                </View>
                <Pressable 
                  style={styles.removePhotoButton}
                  onPress={() => removePhoto(index)}
                >
                  <Text style={styles.removePhotoText}>✕</Text>
                </Pressable>
              </View>
            ))}
          </View>
        )}

        {/* Add Photo Buttons */}
        <View style={styles.photoActions}>
          <Pressable 
            style={({ pressed }) => [
              styles.photoActionButton,
              pressed && styles.buttonPressed
            ]}
            onPress={addPhoto}
          >
            <Text style={styles.photoActionIcon}>📷</Text>
            <Text style={styles.photoActionText}>Take Photo</Text>
          </Pressable>

          <Pressable 
            style={({ pressed }) => [
              styles.photoActionButton,
              pressed && styles.buttonPressed
            ]}
            onPress={addPhoto}
          >
            <Text style={styles.photoActionIcon}>🖼️</Text>
            <Text style={styles.photoActionText}>Choose from Gallery</Text>
          </Pressable>
        </View>

        <View style={styles.helpBox}>
          <Text style={styles.helpIcon}>💡</Text>
          <Text style={styles.helpText}>
            Tip: Clear photos help us give you an accurate quote!
          </Text>
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <Pressable 
          style={({ pressed }) => [
            styles.primaryButton,
            pressed && styles.buttonPressed,
            data.photos.length === 0 && styles.buttonDisabled
          ]}
          onPress={onNext}
          disabled={data.photos.length === 0}
        >
          <Text style={styles.primaryButtonText}>
            Continue with {data.photos.length} {data.photos.length === 1 ? 'photo' : 'photos'} →
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

// ============= SERVICE SCREEN =============
function ServiceScreen({ data, onUpdate, onNext, onBack }: any) {
  const services = [
    { id: 'furniture', icon: '🛋️', name: 'Furniture', description: 'Couches, beds, tables', popular: true, price: 'From $99' },
    { id: 'appliances', icon: '🔌', name: 'Appliances', description: 'Fridges, washers, dryers', popular: true, price: 'From $129' },
    { id: 'construction', icon: '🏗️', name: 'Construction', description: 'Drywall, lumber, debris', popular: false, price: 'From $159' },
    { id: 'electronics', icon: '💻', name: 'Electronics', description: 'TVs, computers, cables', popular: false, price: 'From $79' },
    { id: 'yard-waste', icon: '🌳', name: 'Yard Waste', description: 'Branches, leaves, soil', popular: false, price: 'From $89' },
    { id: 'general', icon: '♻️', name: 'General Junk', description: 'Miscellaneous items', popular: true, price: 'From $69' },
  ];

  return (
    <View style={styles.container}>
      <ScreenHeader 
        title="Service Type"
        subtitle="What do you need removed?"
        onBack={onBack}
        step={3}
        totalSteps={5}
      />
      
      <ScrollView 
        contentContainerStyle={styles.formScrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.serviceGrid}>
          {services.map((service) => (
            <Pressable
              key={service.id}
              style={({ pressed }) => [
                styles.serviceCard,
                data.serviceType === service.id && styles.serviceCardActive,
                pressed && styles.serviceCardPressed
              ]}
              onPress={() => onUpdate({ serviceType: service.id })}
            >
              {service.popular && (
                <View style={styles.popularBadge}>
                  <Text style={styles.popularBadgeText}>POPULAR</Text>
                </View>
              )}
              <Text style={styles.serviceIcon}>{service.icon}</Text>
              <Text style={styles.serviceName}>{service.name}</Text>
              <Text style={styles.serviceDescription}>{service.description}</Text>
              <Text style={styles.servicePrice}>{service.price}</Text>
              {data.serviceType === service.id && (
                <View style={styles.selectedCheckmark}>
                  <Text style={styles.checkmarkText}>✓</Text>
                </View>
              )}
            </Pressable>
          ))}
        </View>

        <View style={styles.formSection}>
          <Text style={styles.fieldLabel}>Additional details (optional)</Text>
          <TextInput
            style={styles.textArea}
            value={data.serviceDetails}
            onChangeText={(text: string) => onUpdate({ serviceDetails: text })}
            placeholder="e.g., 2 sofas, 1 mattress, some boxes..."
            placeholderTextColor={COLORS.muted}
            multiline
            numberOfLines={4}
          />
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <Pressable 
          style={({ pressed }) => [
            styles.primaryButton,
            pressed && styles.buttonPressed,
            !data.serviceType && styles.buttonDisabled
          ]}
          onPress={onNext}
          disabled={!data.serviceType}
        >
          <Text style={styles.primaryButtonText}>Continue →</Text>
        </Pressable>
      </View>
    </View>
  );
}

// ============= DATE/TIME SCREEN =============
function DateTimeScreen({ data, onUpdate, onNext, onBack }: any) {
  const [selectedDate, setSelectedDate] = useState('');
  const dates = getNextDays(7);
  const timeSlots = [
    { id: '8-10', label: '8:00 AM - 10:00 AM', available: true },
    { id: '10-12', label: '10:00 AM - 12:00 PM', available: true, recommended: true },
    { id: '12-2', label: '12:00 PM - 2:00 PM', available: true },
    { id: '2-4', label: '2:00 PM - 4:00 PM', available: false },
    { id: '4-6', label: '4:00 PM - 6:00 PM', available: true },
  ];

  const handleDateSelect = (date: string) => {
    setSelectedDate(date);
    onUpdate({ date });
  };

  const handleTimeSelect = (time: string) => {
    onUpdate({ time });
  };

  return (
    <View style={styles.container}>
      <ScreenHeader 
        title="Schedule Pickup"
        subtitle="When should we come by?"
        onBack={onBack}
        step={4}
        totalSteps={5}
      />
      
      <ScrollView 
        contentContainerStyle={styles.formScrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Date Calendar */}
        <View style={styles.calendarSection}>
          <Text style={styles.fieldLabel}>Select Date</Text>
          <ScrollView 
            horizontal 
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.dateScroll}
          >
            {dates.map((date) => (
              <Pressable
                key={date.full}
                style={({ pressed }) => [
                  styles.dateCard,
                  data.date === date.full && styles.dateCardActive,
                  pressed && styles.dateCardPressed
                ]}
                onPress={() => handleDateSelect(date.full)}
              >
                <Text style={[
                  styles.dateDayName,
                  data.date === date.full && styles.dateTextActive
                ]}>
                  {date.dayName}
                </Text>
                <Text style={[
                  styles.dateDay,
                  data.date === date.full && styles.dateTextActive
                ]}>
                  {date.day}
                </Text>
                <Text style={[
                  styles.dateMonth,
                  data.date === date.full && styles.dateTextActive
                ]}>
                  {date.month}
                </Text>
              </Pressable>
            ))}
          </ScrollView>
        </View>

        {/* Time Slots */}
        {data.date && (
          <View style={styles.timeSection}>
            <Text style={styles.fieldLabel}>Select Time</Text>
            {timeSlots.map((slot) => (
              <Pressable
                key={slot.id}
                style={({ pressed }) => [
                  styles.timeSlot,
                  !slot.available && styles.timeSlotDisabled,
                  data.time === slot.id && styles.timeSlotActive,
                  pressed && slot.available && styles.timeSlotPressed
                ]}
                onPress={() => slot.available && handleTimeSelect(slot.id)}
                disabled={!slot.available}
              >
                <View style={styles.timeSlotContent}>
                  <Text style={[
                    styles.timeSlotText,
                    !slot.available && styles.timeSlotTextDisabled,
                    data.time === slot.id && styles.timeSlotTextActive
                  ]}>
                    {slot.label}
                  </Text>
                  {slot.recommended && (
                    <View style={styles.recommendedBadge}>
                      <Text style={styles.recommendedText}>Recommended</Text>
                    </View>
                  )}
                  {!slot.available && (
                    <Text style={styles.unavailableText}>Unavailable</Text>
                  )}
                </View>
                {data.time === slot.id && (
                  <Text style={styles.timeCheckmark}>✓</Text>
                )}
              </Pressable>
            ))}
          </View>
        )}

        {data.date && !data.time && (
          <View style={styles.helpBox}>
            <Text style={styles.helpIcon}>⏰</Text>
            <Text style={styles.helpText}>
              Most slots fill up fast! Book your preferred time now.
            </Text>
          </View>
        )}
      </ScrollView>

      <View style={styles.footer}>
        <Pressable 
          style={({ pressed }) => [
            styles.primaryButton,
            pressed && styles.buttonPressed,
            (!data.date || !data.time) && styles.buttonDisabled
          ]}
          onPress={onNext}
          disabled={!data.date || !data.time}
        >
          <Text style={styles.primaryButtonText}>Continue →</Text>
        </Pressable>
      </View>
    </View>
  );
}

// ============= CONFIRMATION SCREEN =============
function ConfirmationScreen({ data, onConfirm, onBack }: any) {
  const [loading, setLoading] = useState(false);

  const handleConfirm = async () => {
    setLoading(true);
    // Simulate API call
    setTimeout(() => {
      setLoading(false);
      onConfirm();
    }, 1500);
  };

  const serviceNames: any = {
    furniture: 'Furniture Removal',
    appliances: 'Appliance Removal',
    construction: 'Construction Debris',
    electronics: 'Electronics Disposal',
    'yard-waste': 'Yard Waste',
    general: 'General Junk Removal',
  };

  const timeLabels: any = {
    '8-10': '8:00 AM - 10:00 AM',
    '10-12': '10:00 AM - 12:00 PM',
    '12-2': '12:00 PM - 2:00 PM',
    '2-4': '2:00 PM - 4:00 PM',
    '4-6': '4:00 PM - 6:00 PM',
  };

  return (
    <View style={styles.container}>
      <ScreenHeader 
        title="Confirm Booking"
        subtitle="Review your details"
        onBack={onBack}
        step={5}
        totalSteps={5}
      />
      
      <ScrollView 
        contentContainerStyle={styles.formScrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Summary Card */}
        <View style={styles.summaryCard}>
          <View style={styles.summaryHeader}>
            <Text style={styles.summaryTitle}>Booking Summary</Text>
            <View style={styles.statusBadge}>
              <Text style={styles.statusText}>Pending</Text>
            </View>
          </View>

          <SummaryItem 
            icon="📍"
            label="Pickup Location"
            value={`${data.address}\n${data.city}, ${data.state} ${data.zip}`}
          />

          <SummaryItem 
            icon="📦"
            label="Service"
            value={serviceNames[data.serviceType] || 'Not selected'}
          />

          {data.serviceDetails && (
            <SummaryItem 
              icon="📝"
              label="Details"
              value={data.serviceDetails}
            />
          )}

          <SummaryItem 
            icon="📅"
            label="Date"
            value={data.date}
          />

          <SummaryItem 
            icon="⏰"
            label="Time"
            value={timeLabels[data.time] || 'Not selected'}
          />

          <SummaryItem 
            icon="📸"
            label="Photos"
            value={`${data.photos.length} photo${data.photos.length !== 1 ? 's' : ''} uploaded`}
          />
        </View>

        {/* Price Breakdown */}
        <View style={styles.priceCard}>
          <Text style={styles.priceTitle}>Price Breakdown</Text>
          
          <View style={styles.priceRow}>
            <Text style={styles.priceLabel}>Base Service Fee</Text>
            <Text style={styles.priceValue}>$99.00</Text>
          </View>

          <View style={styles.priceRow}>
            <Text style={styles.priceLabel}>Items (estimated)</Text>
            <Text style={styles.priceValue}>$50.00</Text>
          </View>

          <View style={styles.priceRow}>
            <Text style={styles.priceLabel}>Disposal Fee</Text>
            <Text style={styles.priceValue}>$20.00</Text>
          </View>

          <View style={styles.priceDivider} />

          <View style={styles.priceRow}>
            <Text style={styles.priceTotalLabel}>Estimated Total</Text>
            <Text style={styles.priceTotalValue}>$169.00</Text>
          </View>

          <Text style={styles.priceNote}>
            Final price will be confirmed on arrival
          </Text>
        </View>

        {/* What's Next */}
        <View style={styles.nextStepsCard}>
          <Text style={styles.nextStepsTitle}>What happens next?</Text>
          
          <View style={styles.nextStep}>
            <View style={styles.nextStepIcon}>
              <Text style={styles.nextStepIconText}>1</Text>
            </View>
            <Text style={styles.nextStepText}>
              We'll send a confirmation to your phone
            </Text>
          </View>

          <View style={styles.nextStep}>
            <View style={styles.nextStepIcon}>
              <Text style={styles.nextStepIconText}>2</Text>
            </View>
            <Text style={styles.nextStepText}>
              Our crew will arrive at your scheduled time
            </Text>
          </View>

          <View style={styles.nextStep}>
            <View style={styles.nextStepIcon}>
              <Text style={styles.nextStepIconText}>3</Text>
            </View>
            <Text style={styles.nextStepText}>
              We'll load everything and haul it away!
            </Text>
          </View>
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <Pressable 
          style={({ pressed }) => [
            styles.primaryButton,
            pressed && styles.buttonPressed,
            loading && styles.buttonDisabled
          ]}
          onPress={handleConfirm}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color={COLORS.white} />
          ) : (
            <Text style={styles.primaryButtonText}>Confirm Booking ✓</Text>
          )}
        </Pressable>
      </View>
    </View>
  );
}

// ============= SHARED COMPONENTS =============
function ScreenHeader({ title, subtitle, onBack, step, totalSteps }: any) {
  return (
    <View style={styles.screenHeader}>
      <Pressable onPress={onBack} style={styles.backButton}>
        <Text style={styles.backButtonText}>← Back</Text>
      </Pressable>
      
      <View style={styles.headerContent}>
        <Text style={styles.screenTitle}>{title}</Text>
        <Text style={styles.screenSubtitle}>{subtitle}</Text>
      </View>

      {/* Progress Bar */}
      <View style={styles.progressBar}>
        {Array.from({ length: totalSteps }).map((_, i) => (
          <View
            key={i}
            style={[
              styles.progressDot,
              i < step && styles.progressDotActive,
              i === step - 1 && styles.progressDotCurrent
            ]}
          />
        ))}
      </View>
    </View>
  );
}

function InputField({ label, value, onChangeText, placeholder, error, icon, keyboardType, maxLength }: any) {
  return (
    <View style={styles.inputContainer}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View style={styles.inputWrapper}>
        {icon && <Text style={styles.inputIcon}>{icon}</Text>}
        <TextInput
          style={[
            styles.input,
            error && styles.inputError,
            icon && styles.inputWithIcon
          ]}
          value={value}
          onChangeText={onChangeText}
          placeholder={placeholder}
          placeholderTextColor={COLORS.muted}
          keyboardType={keyboardType}
          maxLength={maxLength}
        />
      </View>
    </View>
  );
}

function SummaryItem({ icon, label, value }: any) {
  return (
    <View style={styles.summaryItem}>
      <Text style={styles.summaryIcon}>{icon}</Text>
      <View style={styles.summaryContent}>
        <Text style={styles.summaryLabel}>{label}</Text>
        <Text style={styles.summaryValue}>{value}</Text>
      </View>
    </View>
  );
}

// ============= UTILITIES =============
function getNextDays(count: number) {
  const days = [];
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  
  for (let i = 0; i < count; i++) {
    const date = new Date();
    date.setDate(date.getDate() + i);
    days.push({
      full: date.toISOString().split('T')[0],
      day: date.getDate(),
      dayName: dayNames[date.getDay()],
      month: monthNames[date.getMonth()],
    });
  }
  
  return days;
}

// ============= STYLES =============
const styles = StyleSheet.create({
  // Container
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  scrollContent: {
    flexGrow: 1,
    paddingBottom: 40,
  },
  formScrollContent: {
    flexGrow: 1,
    padding: 20,
    paddingBottom: 100,
  },

  // Welcome Screen
  welcomeHero: {
    alignItems: 'center',
    paddingTop: 60,
    paddingHorizontal: 24,
  },
  logoPlaceholder: {
    width: 100,
    height: 100,
    borderRadius: 24,
    backgroundColor: COLORS.white,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
    shadowColor: COLORS.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 12,
    elevation: 5,
  },
  logoText: {
    fontSize: 56,
  },
  welcomeTitle: {
    fontSize: 48,
    fontWeight: '800',
    color: COLORS.primary,
    marginBottom: 16,
  },
  gradientBadge: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 24,
    marginBottom: 32,
  },
  tagline: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.white,
  },
  socialProof: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.white,
    padding: 20,
    borderRadius: 16,
    marginBottom: 32,
    width: '100%',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
  },
  proofItem: {
    flex: 1,
    alignItems: 'center',
  },
  proofIcon: {
    fontSize: 24,
    marginBottom: 4,
  },
  proofValue: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.text,
  },
  proofDivider: {
    width: 1,
    height: 40,
    backgroundColor: COLORS.border,
  },
  primaryCTA: {
    backgroundColor: COLORS.cta,
    paddingVertical: 18,
    paddingHorizontal: 48,
    borderRadius: 16,
    width: '100%',
    alignItems: 'center',
    shadowColor: COLORS.cta,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 5,
  },
  primaryCTAText: {
    fontSize: 18,
    fontWeight: '700',
    color: COLORS.white,
  },

  // Features
  featuresSection: {
    padding: 24,
  },
  sectionTitle: {
    fontSize: 24,
    fontWeight: '800',
    color: COLORS.text,
    marginBottom: 20,
  },
  featureCard: {
    flexDirection: 'row',
    backgroundColor: COLORS.white,
    padding: 16,
    borderRadius: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  featureIconContainer: {
    width: 56,
    height: 56,
    borderRadius: 12,
    backgroundColor: COLORS.background,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  featureIcon: {
    fontSize: 28,
  },
  featureContent: {
    flex: 1,
  },
  featureHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  featureTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: COLORS.text,
  },
  stepBadge: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  stepBadgeText: {
    fontSize: 12,
    fontWeight: '700',
    color: COLORS.white,
  },
  featureDescription: {
    fontSize: 14,
    color: COLORS.muted,
  },

  // Trust Section
  trustSection: {
    padding: 24,
    alignItems: 'center',
  },
  trustText: {
    fontSize: 13,
    color: COLORS.muted,
    textAlign: 'center',
    lineHeight: 20,
  },

  // Screen Header
  screenHeader: {
    backgroundColor: COLORS.white,
    paddingTop: 60,
    paddingHorizontal: 20,
    paddingBottom: 20,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  backButton: {
    marginBottom: 16,
  },
  backButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.primary,
  },
  headerContent: {
    marginBottom: 16,
  },
  screenTitle: {
    fontSize: 28,
    fontWeight: '800',
    color: COLORS.text,
    marginBottom: 4,
  },
  screenSubtitle: {
    fontSize: 16,
    color: COLORS.muted,
  },
  progressBar: {
    flexDirection: 'row',
    gap: 8,
  },
  progressDot: {
    flex: 1,
    height: 4,
    backgroundColor: COLORS.border,
    borderRadius: 2,
  },
  progressDotActive: {
    backgroundColor: COLORS.cta,
  },
  progressDotCurrent: {
    backgroundColor: COLORS.primary,
  },

  // Map Placeholder
  mapPlaceholder: {
    height: 200,
    backgroundColor: COLORS.white,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
    borderWidth: 2,
    borderColor: COLORS.border,
    borderStyle: 'dashed',
  },
  mapIcon: {
    fontSize: 48,
    marginBottom: 8,
  },
  mapText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.muted,
    marginBottom: 16,
  },
  locationButton: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 12,
  },
  locationButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.white,
  },

  // Form
  formSection: {
    gap: 16,
  },
  inputContainer: {
    marginBottom: 16,
  },
  fieldLabel: {
    fontSize: 15,
    fontWeight: '600',
    color: COLORS.text,
    marginBottom: 8,
  },
  inputWrapper: {
    position: 'relative',
  },
  input: {
    backgroundColor: COLORS.white,
    borderWidth: 2,
    borderColor: COLORS.border,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    color: COLORS.text,
  },
  inputWithIcon: {
    paddingLeft: 48,
  },
  inputIcon: {
    position: 'absolute',
    left: 16,
    top: 14,
    fontSize: 20,
    zIndex: 1,
  },
  inputError: {
    borderColor: COLORS.error,
  },
  textArea: {
    backgroundColor: COLORS.white,
    borderWidth: 2,
    borderColor: COLORS.border,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    color: COLORS.text,
    height: 100,
    textAlignVertical: 'top',
  },
  row: {
    flexDirection: 'row',
  },

  // Photo Screen
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyStateIcon: {
    fontSize: 64,
    marginBottom: 16,
  },
  emptyStateTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.text,
    marginBottom: 8,
  },
  emptyStateText: {
    fontSize: 16,
    color: COLORS.muted,
    textAlign: 'center',
    paddingHorizontal: 40,
  },
  photoGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 24,
  },
  photoThumbnail: {
    width: (SCREEN_WIDTH - 56) / 3,
    height: (SCREEN_WIDTH - 56) / 3,
    position: 'relative',
  },
  photoPlaceholder: {
    width: '100%',
    height: '100%',
    backgroundColor: COLORS.white,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: COLORS.border,
    justifyContent: 'center',
    alignItems: 'center',
  },
  photoPlaceholderText: {
    fontSize: 32,
  },
  removePhotoButton: {
    position: 'absolute',
    top: -8,
    right: -8,
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: COLORS.error,
    justifyContent: 'center',
    alignItems: 'center',
  },
  removePhotoText: {
    color: COLORS.white,
    fontSize: 14,
    fontWeight: '700',
  },
  photoActions: {
    gap: 12,
    marginBottom: 24,
  },
  photoActionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.white,
    padding: 20,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: COLORS.border,
  },
  photoActionIcon: {
    fontSize: 32,
    marginRight: 16,
  },
  photoActionText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.text,
  },

  // Service Cards
  serviceGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 24,
  },
  serviceCard: {
    width: (SCREEN_WIDTH - 52) / 2,
    backgroundColor: COLORS.white,
    padding: 16,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: COLORS.border,
    position: 'relative',
  },
  serviceCardActive: {
    borderColor: COLORS.primary,
    backgroundColor: '#EEF2FF',
  },
  serviceCardPressed: {
    opacity: 0.7,
  },
  popularBadge: {
    position: 'absolute',
    top: 8,
    right: 8,
    backgroundColor: COLORS.cta,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  popularBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: COLORS.white,
  },
  serviceIcon: {
    fontSize: 40,
    marginBottom: 12,
  },
  serviceName: {
    fontSize: 16,
    fontWeight: '700',
    color: COLORS.text,
    marginBottom: 4,
  },
  serviceDescription: {
    fontSize: 12,
    color: COLORS.muted,
    marginBottom: 8,
  },
  servicePrice: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.primary,
  },
  selectedCheckmark: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  checkmarkText: {
    color: COLORS.white,
    fontSize: 14,
    fontWeight: '700',
  },

  // Date/Time Picker
  calendarSection: {
    marginBottom: 32,
  },
  dateScroll: {
    gap: 12,
    paddingRight: 20,
  },
  dateCard: {
    width: 80,
    backgroundColor: COLORS.white,
    padding: 16,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: COLORS.border,
    alignItems: 'center',
  },
  dateCardActive: {
    borderColor: COLORS.primary,
    backgroundColor: COLORS.primary,
  },
  dateCardPressed: {
    opacity: 0.7,
  },
  dateDayName: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.muted,
    marginBottom: 4,
  },
  dateDay: {
    fontSize: 24,
    fontWeight: '800',
    color: COLORS.text,
    marginBottom: 4,
  },
  dateMonth: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.muted,
  },
  dateTextActive: {
    color: COLORS.white,
  },
  timeSection: {
    gap: 12,
  },
  timeSlot: {
    backgroundColor: COLORS.white,
    padding: 18,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: COLORS.border,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  timeSlotActive: {
    borderColor: COLORS.primary,
    backgroundColor: '#EEF2FF',
  },
  timeSlotDisabled: {
    opacity: 0.5,
  },
  timeSlotPressed: {
    opacity: 0.7,
  },
  timeSlotContent: {
    flex: 1,
  },
  timeSlotText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.text,
  },
  timeSlotTextActive: {
    color: COLORS.primary,
  },
  timeSlotTextDisabled: {
    color: COLORS.muted,
  },
  timeCheckmark: {
    fontSize: 20,
    color: COLORS.primary,
  },
  recommendedBadge: {
    backgroundColor: COLORS.cta,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    marginTop: 4,
    alignSelf: 'flex-start',
  },
  recommendedText: {
    fontSize: 11,
    fontWeight: '700',
    color: COLORS.white,
  },
  unavailableText: {
    fontSize: 12,
    color: COLORS.muted,
    marginTop: 4,
  },

  // Confirmation
  summaryCard: {
    backgroundColor: COLORS.white,
    padding: 20,
    borderRadius: 16,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  summaryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  summaryTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: COLORS.text,
  },
  statusBadge: {
    backgroundColor: '#FEF3C7',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#D97706',
  },
  summaryItem: {
    flexDirection: 'row',
    marginBottom: 16,
  },
  summaryIcon: {
    fontSize: 24,
    marginRight: 12,
    width: 32,
  },
  summaryContent: {
    flex: 1,
  },
  summaryLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.muted,
    marginBottom: 4,
  },
  summaryValue: {
    fontSize: 15,
    fontWeight: '600',
    color: COLORS.text,
  },
  priceCard: {
    backgroundColor: COLORS.white,
    padding: 20,
    borderRadius: 16,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  priceTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: COLORS.text,
    marginBottom: 16,
  },
  priceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  priceLabel: {
    fontSize: 15,
    color: COLORS.muted,
  },
  priceValue: {
    fontSize: 15,
    fontWeight: '600',
    color: COLORS.text,
  },
  priceDivider: {
    height: 1,
    backgroundColor: COLORS.border,
    marginVertical: 12,
  },
  priceTotalLabel: {
    fontSize: 17,
    fontWeight: '800',
    color: COLORS.text,
  },
  priceTotalValue: {
    fontSize: 20,
    fontWeight: '800',
    color: COLORS.primary,
  },
  priceNote: {
    fontSize: 12,
    color: COLORS.muted,
    marginTop: 12,
    fontStyle: 'italic',
  },
  nextStepsCard: {
    backgroundColor: '#ECFDF5',
    padding: 20,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#A7F3D0',
  },
  nextStepsTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: COLORS.text,
    marginBottom: 16,
  },
  nextStep: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  nextStepIcon: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: COLORS.cta,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  nextStepIconText: {
    fontSize: 12,
    fontWeight: '700',
    color: COLORS.white,
  },
  nextStepText: {
    fontSize: 14,
    color: COLORS.text,
    flex: 1,
    paddingTop: 2,
  },

  // Help Box
  helpBox: {
    flexDirection: 'row',
    backgroundColor: '#EEF2FF',
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.secondary,
    marginTop: 16,
  },
  helpIcon: {
    fontSize: 24,
    marginRight: 12,
  },
  helpText: {
    flex: 1,
    fontSize: 14,
    color: COLORS.text,
    lineHeight: 20,
  },

  // Footer
  footer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: COLORS.white,
    padding: 20,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 5,
  },
  primaryButton: {
    backgroundColor: COLORS.cta,
    paddingVertical: 18,
    borderRadius: 16,
    alignItems: 'center',
    shadowColor: COLORS.cta,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 5,
  },
  primaryButtonText: {
    fontSize: 17,
    fontWeight: '700',
    color: COLORS.white,
  },
  buttonPressed: {
    opacity: 0.8,
    transform: [{ scale: 0.98 }],
  },
  buttonDisabled: {
    backgroundColor: COLORS.border,
    shadowOpacity: 0,
    elevation: 0,
  },
});
