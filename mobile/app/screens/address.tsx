import { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, KeyboardAvoidingView, Platform, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { storage } from '../../utils/storage';

export default function AddressScreen() {
  const router = useRouter();
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [zipCode, setZipCode] = useState('');

  useEffect(() => {
    loadDraft();
  }, []);

  const loadDraft = async () => {
    const draft = await storage.getBookingDraft();
    if (draft.address) {
      const parts = draft.address.split('|');
      setAddress(parts[0] || '');
      setCity(parts[1] || '');
      setState(parts[2] || '');
      setZipCode(parts[3] || '');
    }
  };

  const handleContinue = async () => {
    if (!address || !city || !state || !zipCode) {
      return;
    }

    const fullAddress = `${address}|${city}|${state}|${zipCode}`;
    await storage.saveBookingDraft({ address: fullAddress });
    router.push('/screens/photos');
  };

  const isValid = address && city && state && zipCode.length === 5;

  return (
    <KeyboardAvoidingView 
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      className="flex-1 bg-white"
    >
      <ScrollView className="flex-1">
        <View className="p-6">
          <Text className="text-2xl font-bold text-gray-900 mb-2">
            Where do you need service?
          </Text>
          <Text className="text-base text-gray-500 mb-8">
            Enter the address where we should pick up your items
          </Text>

          <View className="space-y-4">
            <View>
              <Text className="text-sm font-medium text-gray-700 mb-2">Street Address</Text>
              <TextInput
                className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-4 text-base"
                placeholder="123 Main St"
                value={address}
                onChangeText={setAddress}
                autoComplete="street-address"
              />
            </View>

            <View>
              <Text className="text-sm font-medium text-gray-700 mb-2">City</Text>
              <TextInput
                className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-4 text-base"
                placeholder="San Francisco"
                value={city}
                onChangeText={setCity}
                autoComplete="address-level2"
              />
            </View>

            <View className="flex-row space-x-4">
              <View className="flex-1">
                <Text className="text-sm font-medium text-gray-700 mb-2">State</Text>
                <TextInput
                  className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-4 text-base"
                  placeholder="CA"
                  value={state}
                  onChangeText={(text) => setState(text.toUpperCase())}
                  maxLength={2}
                  autoCapitalize="characters"
                  autoComplete="address-level1"
                />
              </View>

              <View className="flex-1">
                <Text className="text-sm font-medium text-gray-700 mb-2">ZIP Code</Text>
                <TextInput
                  className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-4 text-base"
                  placeholder="94102"
                  value={zipCode}
                  onChangeText={setZipCode}
                  keyboardType="number-pad"
                  maxLength={5}
                  autoComplete="postal-code"
                />
              </View>
            </View>
          </View>
        </View>
      </ScrollView>

      <View className="p-6 border-t border-gray-100">
        <TouchableOpacity
          className={`bg-primary rounded-xl py-4 items-center ${!isValid ? 'opacity-50' : ''}`}
          onPress={handleContinue}
          disabled={!isValid}
        >
          <Text className="text-white text-lg font-semibold">Continue</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}
