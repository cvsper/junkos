import { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, TextInput, ScrollView, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { storage } from '../../utils/storage';

const SERVICE_TYPES = [
  { id: 'furniture', label: 'Furniture', emoji: '🛋️' },
  { id: 'appliances', label: 'Appliances', emoji: '🔌' },
  { id: 'electronics', label: 'Electronics', emoji: '📱' },
  { id: 'yard-waste', label: 'Yard Waste', emoji: '🌿' },
  { id: 'construction', label: 'Construction', emoji: '🔨' },
  { id: 'other', label: 'Other', emoji: '📦' },
];

export default function ServiceScreen() {
  const router = useRouter();
  const [selectedType, setSelectedType] = useState('');
  const [details, setDetails] = useState('');

  useEffect(() => {
    loadDraft();
  }, []);

  const loadDraft = async () => {
    const draft = await storage.getBookingDraft();
    if (draft.serviceType) setSelectedType(draft.serviceType);
    if (draft.serviceDetails) setDetails(draft.serviceDetails);
  };

  const handleContinue = async () => {
    if (!selectedType) {
      Alert.alert('Selection Required', 'Please select a service type');
      return;
    }

    await storage.saveBookingDraft({
      serviceType: selectedType,
      serviceDetails: details,
    });

    router.push('/screens/datetime');
  };

  return (
    <View className="flex-1 bg-white">
      <ScrollView className="flex-1">
        <View className="p-6">
          <Text className="text-2xl font-bold text-gray-900 mb-2">
            What needs to be removed?
          </Text>
          <Text className="text-base text-gray-500 mb-6">
            Select the type of items and add any details
          </Text>

          <View className="mb-6">
            <Text className="text-sm font-medium text-gray-700 mb-3">Service Type</Text>
            <View className="flex-row flex-wrap -m-2">
              {SERVICE_TYPES.map((type) => (
                <View key={type.id} className="w-1/2 p-2">
                  <TouchableOpacity
                    className={`rounded-xl p-4 border-2 ${
                      selectedType === type.id
                        ? 'border-primary bg-blue-50'
                        : 'border-gray-200 bg-white'
                    }`}
                    onPress={() => setSelectedType(type.id)}
                  >
                    <Text className="text-3xl mb-2">{type.emoji}</Text>
                    <Text
                      className={`text-base font-semibold ${
                        selectedType === type.id ? 'text-primary' : 'text-gray-900'
                      }`}
                    >
                      {type.label}
                    </Text>
                  </TouchableOpacity>
                </View>
              ))}
            </View>
          </View>

          <View>
            <Text className="text-sm font-medium text-gray-700 mb-2">
              Additional Details (Optional)
            </Text>
            <TextInput
              className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-4 text-base"
              placeholder="E.g., 2 sofas, 1 mattress, very heavy"
              value={details}
              onChangeText={setDetails}
              multiline
              numberOfLines={4}
              textAlignVertical="top"
            />
            <Text className="text-sm text-gray-400 mt-2">
              Help us prepare by describing size, weight, or special considerations
            </Text>
          </View>
        </View>
      </ScrollView>

      <View className="p-6 border-t border-gray-100">
        <TouchableOpacity
          className={`bg-primary rounded-xl py-4 items-center ${!selectedType ? 'opacity-50' : ''}`}
          onPress={handleContinue}
          disabled={!selectedType}
        >
          <Text className="text-white text-lg font-semibold">Continue</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
