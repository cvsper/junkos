import { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Alert, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { storage, BookingData } from '../../utils/storage';
import { api } from '../../utils/api';

export default function ConfirmationScreen() {
  const router = useRouter();
  const [booking, setBooking] = useState<BookingData>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadBooking();
  }, []);

  const loadBooking = async () => {
    const data = await storage.getBookingDraft();
    setBooking(data);
  };

  const formatAddress = (address?: string) => {
    if (!address) return 'Not provided';
    const parts = address.split('|');
    return `${parts[0]}, ${parts[1]}, ${parts[2]} ${parts[3]}`;
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Not selected';
    const date = new Date(dateString + 'T00:00:00');
    return date.toLocaleDateString('en-US', { 
      weekday: 'long', 
      year: 'numeric', 
      month: 'long', 
      day: 'numeric' 
    });
  };

  const getServiceTypeLabel = (type?: string) => {
    const types: Record<string, string> = {
      'furniture': '🛋️ Furniture',
      'appliances': '🔌 Appliances',
      'electronics': '📱 Electronics',
      'yard-waste': '🌿 Yard Waste',
      'construction': '🔨 Construction',
      'other': '📦 Other',
    };
    return type ? types[type] : 'Not selected';
  };

  const handleConfirm = async () => {
    setLoading(true);

    try {
      // Upload photos first
      const photoUrls: string[] = [];
      if (booking.photos) {
        for (const photoUri of booking.photos) {
          const result = await api.uploadPhoto(photoUri);
          if (result.url) {
            photoUrls.push(result.url);
          }
        }
      }

      // Create booking
      const bookingData = {
        address: formatAddress(booking.address),
        serviceType: booking.serviceType,
        serviceDetails: booking.serviceDetails,
        scheduledDate: booking.scheduledDate,
        scheduledTime: booking.scheduledTime,
        photos: photoUrls,
      };

      const response = await api.createBooking(bookingData);

      if (response.error) {
        Alert.alert('Booking Failed', response.error);
        setLoading(false);
        return;
      }

      // Clear draft
      await storage.clearBookingDraft();

      Alert.alert(
        'Booking Confirmed! 🎉',
        'Your junk removal service has been scheduled. We\'ll send you a confirmation email shortly.',
        [
          {
            text: 'Done',
            onPress: () => router.replace('/'),
          },
        ]
      );
    } catch (error) {
      Alert.alert('Error', 'Failed to create booking. Please try again.');
      setLoading(false);
    }
  };

  return (
    <View className="flex-1 bg-white">
      <ScrollView className="flex-1">
        <View className="p-6">
          <Text className="text-2xl font-bold text-gray-900 mb-2">
            Review Your Booking
          </Text>
          <Text className="text-base text-gray-500 mb-6">
            Please confirm all details are correct
          </Text>

          <View className="space-y-4">
            {/* Address */}
            <View className="bg-gray-50 rounded-xl p-4">
              <Text className="text-xs font-semibold text-gray-500 uppercase mb-1">
                Service Address
              </Text>
              <Text className="text-base text-gray-900">
                {formatAddress(booking.address)}
              </Text>
            </View>

            {/* Photos */}
            <View className="bg-gray-50 rounded-xl p-4">
              <Text className="text-xs font-semibold text-gray-500 uppercase mb-1">
                Photos
              </Text>
              <Text className="text-base text-gray-900">
                {booking.photos?.length || 0} photo{booking.photos?.length !== 1 ? 's' : ''} uploaded
              </Text>
            </View>

            {/* Service Type */}
            <View className="bg-gray-50 rounded-xl p-4">
              <Text className="text-xs font-semibold text-gray-500 uppercase mb-1">
                Service Type
              </Text>
              <Text className="text-base text-gray-900">
                {getServiceTypeLabel(booking.serviceType)}
              </Text>
              {booking.serviceDetails && (
                <Text className="text-sm text-gray-600 mt-2">
                  {booking.serviceDetails}
                </Text>
              )}
            </View>

            {/* Date & Time */}
            <View className="bg-gray-50 rounded-xl p-4">
              <Text className="text-xs font-semibold text-gray-500 uppercase mb-1">
                Scheduled
              </Text>
              <Text className="text-base text-gray-900">
                {formatDate(booking.scheduledDate)}
              </Text>
              <Text className="text-base text-gray-900 mt-1">
                {booking.scheduledTime || 'No time selected'}
              </Text>
            </View>
          </View>

          <View className="mt-6 bg-blue-50 rounded-xl p-4">
            <Text className="text-sm text-gray-700">
              📋 <Text className="font-semibold">What happens next?</Text>
              {'\n'}• You'll receive a confirmation email
              {'\n'}• Our team will arrive during your time window
              {'\n'}• Payment is collected after service completion
              {'\n'}• We handle all loading and disposal
            </Text>
          </View>
        </View>
      </ScrollView>

      <View className="p-6 border-t border-gray-100">
        <TouchableOpacity
          className={`bg-success rounded-xl py-4 items-center ${loading ? 'opacity-50' : ''}`}
          onPress={handleConfirm}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="white" />
          ) : (
            <Text className="text-white text-lg font-semibold">Confirm Booking</Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          className="items-center mt-4"
          onPress={() => router.back()}
          disabled={loading}
        >
          <Text className="text-gray-600 text-base">Go Back</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
