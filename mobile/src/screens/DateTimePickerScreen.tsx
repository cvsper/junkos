import React, { useState } from 'react';
import { View, StyleSheet, ScrollView, Alert, Platform } from 'react-native';
import { Button, Text, RadioButton } from 'react-native-paper';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { SafeAreaView } from 'react-native-safe-area-context';
import DateTimePicker from '@react-native-community/datetimepicker';
import { colors } from '../theme';
import { RootStackParamList, Booking } from '../types';
import { bookingsApi } from '../api/bookings';

type Props = NativeStackScreenProps<RootStackParamList, 'DateTimePicker'>;

const TIME_SLOTS = [
  { label: 'Morning (8am - 12pm)', value: '8:00 AM' },
  { label: 'Afternoon (12pm - 4pm)', value: '12:00 PM' },
  { label: 'Evening (4pm - 8pm)', value: '4:00 PM' },
];

export default function DateTimePickerScreen({ navigation, route }: Props) {
  const { address, photos, items } = route.params;
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [selectedTimeSlot, setSelectedTimeSlot] = useState(TIME_SLOTS[0].value);
  const [estimatedPrice, setEstimatedPrice] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  const minDate = new Date();
  const maxDate = new Date();
  maxDate.setDate(maxDate.getDate() + 60); // Allow booking up to 60 days ahead

  const handleDateChange = (event: any, date?: Date) => {
    setShowDatePicker(Platform.OS === 'ios');
    if (date) {
      setSelectedDate(date);
      getEstimate(date);
    }
  };

  const getEstimate = async (date: Date) => {
    setLoading(true);
    try {
      const response = await bookingsApi.estimatePrice(items, address);
      setEstimatedPrice(response.estimatedPrice);
    } catch (error) {
      console.error('Error getting estimate:', error);
      Alert.alert('Error', 'Failed to get price estimate');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (date: Date) => {
    return date.toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const handleContinue = () => {
    const booking: Booking = {
      address,
      items,
      photos,
      scheduledDate: selectedDate.toISOString().split('T')[0],
      scheduledTime: selectedTimeSlot,
      estimatedPrice: estimatedPrice || undefined,
    };

    navigation.navigate('Payment', { booking });
  };

  React.useEffect(() => {
    getEstimate(selectedDate);
  }, []);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Text style={styles.title}>When should we come?</Text>
          <Text style={styles.subtitle}>Choose your preferred date and time</Text>
        </View>

        <View style={styles.dateSection}>
          <Text style={styles.sectionTitle}>📅 Select Date</Text>
          <Button
            mode="outlined"
            onPress={() => setShowDatePicker(true)}
            style={styles.dateButton}
            contentStyle={styles.dateButtonContent}
          >
            {formatDate(selectedDate)}
          </Button>
          {showDatePicker && (
            <DateTimePicker
              value={selectedDate}
              mode="date"
              display={Platform.OS === 'ios' ? 'spinner' : 'default'}
              onChange={handleDateChange}
              minimumDate={minDate}
              maximumDate={maxDate}
              textColor={colors.text}
            />
          )}
        </View>

        <View style={styles.timeSection}>
          <Text style={styles.sectionTitle}>🕐 Select Time Window</Text>
          <RadioButton.Group
            onValueChange={(value) => setSelectedTimeSlot(value)}
            value={selectedTimeSlot}
          >
            {TIME_SLOTS.map((slot) => (
              <View key={slot.value} style={styles.radioItem}>
                <RadioButton.Item
                  label={slot.label}
                  value={slot.value}
                  style={styles.radio}
                  labelStyle={styles.radioLabel}
                  color={colors.primary}
                />
              </View>
            ))}
          </RadioButton.Group>
        </View>

        {estimatedPrice !== null && (
          <View style={styles.estimateCard}>
            <Text style={styles.estimateTitle}>💰 Estimated Price</Text>
            <Text style={styles.estimatePrice}>${estimatedPrice.toFixed(2)}</Text>
            <Text style={styles.estimateNote}>
              Final price may vary based on actual volume and weight
            </Text>
          </View>
        )}

        <View style={styles.infoCard}>
          <Text style={styles.infoTitle}>ℹ️ What to Expect</Text>
          <Text style={styles.infoText}>
            • Our team will arrive during your selected time window
          </Text>
          <Text style={styles.infoText}>
            • We'll provide a final quote before starting work
          </Text>
          <Text style={styles.infoText}>
            • All labor, hauling, and disposal included
          </Text>
          <Text style={styles.infoText}>
            • We'll clean up when we're done
          </Text>
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <Button
          mode="contained"
          onPress={handleContinue}
          style={styles.continueButton}
          labelStyle={styles.continueButtonLabel}
          contentStyle={styles.buttonContent}
          disabled={loading}
        >
          Continue to Payment
        </Button>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 100,
  },
  header: {
    marginBottom: 24,
  },
  title: {
    fontSize: 24,
    fontFamily: 'Poppins-SemiBold',
    color: colors.text,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    fontFamily: 'OpenSans-Regular',
    color: colors.muted,
  },
  dateSection: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontFamily: 'Poppins-SemiBold',
    color: colors.text,
    marginBottom: 16,
  },
  dateButton: {
    borderRadius: 12,
    borderColor: colors.primary,
  },
  dateButtonContent: {
    paddingVertical: 12,
  },
  timeSection: {
    marginBottom: 24,
  },
  radioItem: {
    backgroundColor: colors.white,
    borderRadius: 12,
    marginBottom: 12,
    overflow: 'hidden',
  },
  radio: {
    paddingVertical: 8,
  },
  radioLabel: {
    fontFamily: 'OpenSans-Regular',
    fontSize: 16,
  },
  estimateCard: {
    backgroundColor: colors.white,
    padding: 24,
    borderRadius: 12,
    marginBottom: 24,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: colors.cta,
  },
  estimateTitle: {
    fontSize: 16,
    fontFamily: 'Poppins-Medium',
    color: colors.muted,
    marginBottom: 8,
  },
  estimatePrice: {
    fontSize: 42,
    fontFamily: 'Poppins-Bold',
    color: colors.cta,
    marginBottom: 8,
  },
  estimateNote: {
    fontSize: 12,
    fontFamily: 'OpenSans-Regular',
    color: colors.muted,
    textAlign: 'center',
  },
  infoCard: {
    backgroundColor: '#EFF6FF',
    padding: 20,
    borderRadius: 12,
    borderLeftWidth: 4,
    borderLeftColor: colors.info,
  },
  infoTitle: {
    fontSize: 16,
    fontFamily: 'Poppins-SemiBold',
    color: colors.text,
    marginBottom: 12,
  },
  infoText: {
    fontSize: 14,
    fontFamily: 'OpenSans-Regular',
    color: colors.text,
    marginBottom: 8,
    lineHeight: 20,
  },
  footer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    padding: 24,
    backgroundColor: colors.white,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  continueButton: {
    backgroundColor: colors.cta,
    borderRadius: 12,
  },
  continueButtonLabel: {
    fontSize: 16,
    fontFamily: 'Poppins-SemiBold',
    color: colors.white,
  },
  buttonContent: {
    paddingVertical: 8,
  },
});
