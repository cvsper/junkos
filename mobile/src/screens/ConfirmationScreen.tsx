import React, { useEffect, useState } from 'react';
import { View, StyleSheet, ScrollView } from 'react-native';
import { Button, Text, ActivityIndicator } from 'react-native-paper';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '../theme';
import { RootStackParamList, Booking } from '../types';
import { bookingsApi } from '../api/bookings';

type Props = NativeStackScreenProps<RootStackParamList, 'Confirmation'>;

export default function ConfirmationScreen({ navigation, route }: Props) {
  const { bookingId } = route.params;
  const [booking, setBooking] = useState<Booking | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadBooking();
  }, []);

  const loadBooking = async () => {
    try {
      const data = await bookingsApi.getById(bookingId);
      setBooking(data);
    } catch (error) {
      console.error('Error loading booking:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDone = () => {
    navigation.navigate('Welcome');
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.successIcon}>
          <Text style={styles.checkmark}>✓</Text>
        </View>

        <Text style={styles.title}>Booking Confirmed!</Text>
        <Text style={styles.subtitle}>
          We've received your hauling request
        </Text>

        {booking && (
          <>
            <View style={styles.detailsCard}>
              <Text style={styles.cardTitle}>📋 Booking Details</Text>
              
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Booking ID:</Text>
                <Text style={styles.detailValue}>#{booking.id}</Text>
              </View>

              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>📍 Location:</Text>
                <Text style={styles.detailValue}>
                  {booking.address.street}{'\n'}
                  {booking.address.city}, {booking.address.state} {booking.address.zipCode}
                </Text>
              </View>

              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>📅 Scheduled Date:</Text>
                <Text style={styles.detailValue}>{booking.scheduledDate}</Text>
              </View>

              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>🕐 Time Window:</Text>
                <Text style={styles.detailValue}>{booking.scheduledTime}</Text>
              </View>

              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>📦 Items:</Text>
                <View style={styles.itemsList}>
                  {booking.items.map((item, index) => (
                    <Text key={index} style={styles.itemText}>
                      • {item.name} (x{item.quantity})
                    </Text>
                  ))}
                </View>
              </View>

              {booking.estimatedPrice && (
                <View style={styles.priceRow}>
                  <Text style={styles.priceLabel}>Estimated Total:</Text>
                  <Text style={styles.priceValue}>
                    ${booking.estimatedPrice.toFixed(2)}
                  </Text>
                </View>
              )}
            </View>

            <View style={styles.nextStepsCard}>
              <Text style={styles.cardTitle}>✅ What's Next?</Text>
              
              <View style={styles.stepItem}>
                <Text style={styles.stepNumber}>1</Text>
                <View style={styles.stepContent}>
                  <Text style={styles.stepTitle}>Confirmation Email</Text>
                  <Text style={styles.stepText}>
                    Check your email for booking confirmation and details
                  </Text>
                </View>
              </View>

              <View style={styles.stepItem}>
                <Text style={styles.stepNumber}>2</Text>
                <View style={styles.stepContent}>
                  <Text style={styles.stepTitle}>Team Assignment</Text>
                  <Text style={styles.stepText}>
                    We'll assign a crew and send you their details
                  </Text>
                </View>
              </View>

              <View style={styles.stepItem}>
                <Text style={styles.stepNumber}>3</Text>
                <View style={styles.stepContent}>
                  <Text style={styles.stepTitle}>Day Before Reminder</Text>
                  <Text style={styles.stepText}>
                    You'll receive a reminder 24 hours before pickup
                  </Text>
                </View>
              </View>

              <View style={styles.stepItem}>
                <Text style={styles.stepNumber}>4</Text>
                <View style={styles.stepContent}>
                  <Text style={styles.stepTitle}>Pickup Day</Text>
                  <Text style={styles.stepText}>
                    Our team will arrive during your time window
                  </Text>
                </View>
              </View>
            </View>

            <View style={styles.supportCard}>
              <Text style={styles.supportIcon}>💬</Text>
              <Text style={styles.supportTitle}>Need Help?</Text>
              <Text style={styles.supportText}>
                Contact us anytime at support@goumuve.com{'\n'}
                or call (555) 123-4567
              </Text>
            </View>
          </>
        )}
      </ScrollView>

      <View style={styles.footer}>
        <Button
          mode="contained"
          onPress={handleDone}
          style={styles.doneButton}
          labelStyle={styles.doneButtonLabel}
          contentStyle={styles.buttonContent}
        >
          Done
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
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingTop: 32,
    paddingBottom: 100,
    alignItems: 'center',
  },
  successIcon: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: colors.success,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  checkmark: {
    fontSize: 60,
    color: colors.white,
    fontFamily: 'Poppins-Bold',
  },
  title: {
    fontSize: 28,
    fontFamily: 'Poppins-Bold',
    color: colors.text,
    marginBottom: 8,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 16,
    fontFamily: 'OpenSans-Regular',
    color: colors.muted,
    textAlign: 'center',
    marginBottom: 32,
  },
  detailsCard: {
    backgroundColor: colors.white,
    padding: 20,
    borderRadius: 12,
    marginBottom: 16,
    width: '100%',
  },
  cardTitle: {
    fontSize: 18,
    fontFamily: 'Poppins-SemiBold',
    color: colors.text,
    marginBottom: 16,
  },
  detailRow: {
    marginBottom: 16,
  },
  detailLabel: {
    fontSize: 14,
    fontFamily: 'OpenSans-SemiBold',
    color: colors.muted,
    marginBottom: 4,
  },
  detailValue: {
    fontSize: 14,
    fontFamily: 'OpenSans-Regular',
    color: colors.text,
    lineHeight: 20,
  },
  itemsList: {
    marginTop: 4,
  },
  itemText: {
    fontSize: 14,
    fontFamily: 'OpenSans-Regular',
    color: colors.text,
    marginBottom: 4,
  },
  priceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  priceLabel: {
    fontSize: 16,
    fontFamily: 'Poppins-SemiBold',
    color: colors.text,
  },
  priceValue: {
    fontSize: 20,
    fontFamily: 'Poppins-Bold',
    color: colors.success,
  },
  nextStepsCard: {
    backgroundColor: colors.white,
    padding: 20,
    borderRadius: 12,
    marginBottom: 16,
    width: '100%',
  },
  stepItem: {
    flexDirection: 'row',
    marginBottom: 16,
  },
  stepNumber: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.primary,
    color: colors.white,
    fontSize: 16,
    fontFamily: 'Poppins-SemiBold',
    textAlign: 'center',
    lineHeight: 32,
    marginRight: 12,
  },
  stepContent: {
    flex: 1,
  },
  stepTitle: {
    fontSize: 16,
    fontFamily: 'Poppins-SemiBold',
    color: colors.text,
    marginBottom: 4,
  },
  stepText: {
    fontSize: 14,
    fontFamily: 'OpenSans-Regular',
    color: colors.muted,
    lineHeight: 20,
  },
  supportCard: {
    backgroundColor: '#EFF6FF',
    padding: 20,
    borderRadius: 12,
    alignItems: 'center',
    width: '100%',
  },
  supportIcon: {
    fontSize: 32,
    marginBottom: 8,
  },
  supportTitle: {
    fontSize: 16,
    fontFamily: 'Poppins-SemiBold',
    color: colors.text,
    marginBottom: 8,
  },
  supportText: {
    fontSize: 14,
    fontFamily: 'OpenSans-Regular',
    color: colors.muted,
    textAlign: 'center',
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
  doneButton: {
    backgroundColor: colors.primary,
    borderRadius: 12,
  },
  doneButtonLabel: {
    fontSize: 16,
    fontFamily: 'Poppins-SemiBold',
    color: colors.white,
  },
  buttonContent: {
    paddingVertical: 8,
  },
});
