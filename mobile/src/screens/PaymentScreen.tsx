import React, { useState, useEffect } from 'react';
import { View, StyleSheet, ScrollView, Alert } from 'react-native';
import { Button, Text, ActivityIndicator } from 'react-native-paper';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { SafeAreaView } from 'react-native-safe-area-context';
import { CardField, useStripe } from '@stripe/stripe-react-native';
import { colors } from '../theme';
import { RootStackParamList } from '../types';
import { bookingsApi } from '../api/bookings';

type Props = NativeStackScreenProps<RootStackParamList, 'Payment'>;

export default function PaymentScreen({ navigation, route }: Props) {
  const { booking } = route.params;
  const { confirmPayment } = useStripe();
  const [loading, setLoading] = useState(false);
  const [cardComplete, setCardComplete] = useState(false);
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [bookingId, setBookingId] = useState<number | null>(null);

  useEffect(() => {
    createBooking();
  }, []);

  const createBooking = async () => {
    setLoading(true);
    try {
      // Create booking first
      const createdBooking = await bookingsApi.create(booking);
      setBookingId(createdBooking.id!);

      // Create payment intent
      const paymentIntent = await bookingsApi.createPaymentIntent(createdBooking.id!);
      setClientSecret(paymentIntent.clientSecret);
    } catch (error) {
      console.error('Error creating booking:', error);
      Alert.alert('Error', 'Failed to initialize payment. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handlePayment = async () => {
    if (!clientSecret || !bookingId) {
      Alert.alert('Error', 'Payment not ready. Please try again.');
      return;
    }

    if (!cardComplete) {
      Alert.alert('Error', 'Please enter complete card details');
      return;
    }

    setLoading(true);
    try {
      const { error, paymentIntent } = await confirmPayment(clientSecret, {
        paymentMethodType: 'Card',
      });

      if (error) {
        Alert.alert('Payment Failed', error.message);
        return;
      }

      if (paymentIntent?.status === 'Succeeded') {
        // Confirm payment on backend
        await bookingsApi.confirmPayment(bookingId, paymentIntent.id);
        navigation.replace('Confirmation', { bookingId });
      }
    } catch (error: any) {
      console.error('Payment error:', error);
      Alert.alert('Error', 'Payment failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const formatPrice = (price?: number) => {
    if (!price) return '$0.00';
    return `$${price.toFixed(2)}`;
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Text style={styles.title}>Secure Payment</Text>
          <Text style={styles.subtitle}>Complete your booking with Stripe</Text>
        </View>

        <View style={styles.summaryCard}>
          <Text style={styles.summaryTitle}>Booking Summary</Text>
          
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>📍 Location:</Text>
            <Text style={styles.summaryValue} numberOfLines={2}>
              {booking.address.street}, {booking.address.city}
            </Text>
          </View>

          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>📅 Date:</Text>
            <Text style={styles.summaryValue}>{booking.scheduledDate}</Text>
          </View>

          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>🕐 Time:</Text>
            <Text style={styles.summaryValue}>{booking.scheduledTime}</Text>
          </View>

          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>📦 Items:</Text>
            <Text style={styles.summaryValue}>
              {booking.items.map((i) => i.name).join(', ')}
            </Text>
          </View>

          <View style={styles.divider} />

          <View style={styles.totalRow}>
            <Text style={styles.totalLabel}>Estimated Total:</Text>
            <Text style={styles.totalValue}>
              {formatPrice(booking.estimatedPrice)}
            </Text>
          </View>
        </View>

        <View style={styles.paymentSection}>
          <Text style={styles.sectionTitle}>💳 Payment Method</Text>
          
          <View style={styles.cardFieldContainer}>
            <CardField
              postalCodeEnabled={true}
              placeholder={{
                number: '4242 4242 4242 4242',
              }}
              cardStyle={styles.cardStyle}
              style={styles.cardField}
              onCardChange={(cardDetails) => {
                setCardComplete(cardDetails.complete);
              }}
            />
          </View>

          <View style={styles.securityNote}>
            <Text style={styles.securityIcon}>🔒</Text>
            <Text style={styles.securityText}>
              Your payment information is encrypted and secure. We use Stripe for
              payment processing.
            </Text>
          </View>
        </View>

        <View style={styles.disclaimerCard}>
          <Text style={styles.disclaimerText}>
            <Text style={styles.disclaimerBold}>Note:</Text> This is an estimated price.
            The final amount may be adjusted based on the actual volume and weight of items.
            You'll be notified of any changes before work begins.
          </Text>
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <Button
          mode="contained"
          onPress={handlePayment}
          style={styles.payButton}
          labelStyle={styles.payButtonLabel}
          contentStyle={styles.buttonContent}
          disabled={loading || !clientSecret}
        >
          {loading ? (
            <ActivityIndicator color={colors.white} />
          ) : (
            `Pay ${formatPrice(booking.estimatedPrice)}`
          )}
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
  summaryCard: {
    backgroundColor: colors.white,
    padding: 20,
    borderRadius: 12,
    marginBottom: 24,
  },
  summaryTitle: {
    fontSize: 18,
    fontFamily: 'Poppins-SemiBold',
    color: colors.text,
    marginBottom: 16,
  },
  summaryRow: {
    marginBottom: 12,
  },
  summaryLabel: {
    fontSize: 14,
    fontFamily: 'OpenSans-SemiBold',
    color: colors.muted,
    marginBottom: 4,
  },
  summaryValue: {
    fontSize: 14,
    fontFamily: 'OpenSans-Regular',
    color: colors.text,
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: 16,
  },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  totalLabel: {
    fontSize: 18,
    fontFamily: 'Poppins-SemiBold',
    color: colors.text,
  },
  totalValue: {
    fontSize: 24,
    fontFamily: 'Poppins-Bold',
    color: colors.cta,
  },
  paymentSection: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontFamily: 'Poppins-SemiBold',
    color: colors.text,
    marginBottom: 16,
  },
  cardFieldContainer: {
    backgroundColor: colors.white,
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
  },
  cardField: {
    height: 50,
  },
  cardStyle: {
    backgroundColor: colors.white,
    textColor: colors.text,
    placeholderColor: colors.muted,
  },
  securityNote: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EFF6FF',
    padding: 16,
    borderRadius: 12,
  },
  securityIcon: {
    fontSize: 24,
    marginRight: 12,
  },
  securityText: {
    flex: 1,
    fontSize: 14,
    fontFamily: 'OpenSans-Regular',
    color: colors.text,
    lineHeight: 20,
  },
  disclaimerCard: {
    backgroundColor: '#FEF3C7',
    padding: 16,
    borderRadius: 12,
    borderLeftWidth: 4,
    borderLeftColor: colors.warning,
  },
  disclaimerText: {
    fontSize: 14,
    fontFamily: 'OpenSans-Regular',
    color: colors.text,
    lineHeight: 20,
  },
  disclaimerBold: {
    fontFamily: 'OpenSans-SemiBold',
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
  payButton: {
    backgroundColor: colors.cta,
    borderRadius: 12,
  },
  payButtonLabel: {
    fontSize: 16,
    fontFamily: 'Poppins-SemiBold',
    color: colors.white,
  },
  buttonContent: {
    paddingVertical: 8,
  },
});
