import { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, Image, ScrollView, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { storage } from '../../utils/storage';

export default function PhotosScreen() {
  const router = useRouter();
  const [photos, setPhotos] = useState<string[]>([]);

  useEffect(() => {
    loadDraft();
  }, []);

  const loadDraft = async () => {
    const draft = await storage.getBookingDraft();
    if (draft.photos) {
      setPhotos(draft.photos);
    }
  };

  const requestPermissions = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission Required', 'Camera permission is needed to take photos');
      return false;
    }
    return true;
  };

  const takePhoto = async () => {
    const hasPermission = await requestPermissions();
    if (!hasPermission) return;

    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [4, 3],
      quality: 0.8,
    });

    if (!result.canceled && result.assets[0]) {
      const newPhotos = [...photos, result.assets[0].uri];
      setPhotos(newPhotos);
      await storage.saveBookingDraft({ photos: newPhotos });
    }
  };

  const pickPhoto = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [4, 3],
      quality: 0.8,
    });

    if (!result.canceled && result.assets[0]) {
      const newPhotos = [...photos, result.assets[0].uri];
      setPhotos(newPhotos);
      await storage.saveBookingDraft({ photos: newPhotos });
    }
  };

  const removePhoto = (index: number) => {
    const newPhotos = photos.filter((_, i) => i !== index);
    setPhotos(newPhotos);
    storage.saveBookingDraft({ photos: newPhotos });
  };

  const handleContinue = () => {
    if (photos.length === 0) {
      Alert.alert('Photos Required', 'Please add at least one photo of the items');
      return;
    }
    router.push('/screens/service');
  };

  return (
    <View className="flex-1 bg-white">
      <ScrollView className="flex-1">
        <View className="p-6">
          <Text className="text-2xl font-bold text-gray-900 mb-2">
            Add Photos
          </Text>
          <Text className="text-base text-gray-500 mb-6">
            Take photos of the items you need removed
          </Text>

          <View className="flex-row space-x-4 mb-6">
            <TouchableOpacity
              className="flex-1 bg-primary rounded-xl py-4 items-center"
              onPress={takePhoto}
            >
              <Text className="text-white text-base font-semibold">📷 Take Photo</Text>
            </TouchableOpacity>

            <TouchableOpacity
              className="flex-1 bg-gray-100 rounded-xl py-4 items-center"
              onPress={pickPhoto}
            >
              <Text className="text-gray-700 text-base font-semibold">🖼️ Gallery</Text>
            </TouchableOpacity>
          </View>

          {photos.length > 0 && (
            <View>
              <Text className="text-lg font-semibold text-gray-900 mb-4">
                {photos.length} Photo{photos.length !== 1 ? 's' : ''}
              </Text>
              <View className="flex-row flex-wrap">
                {photos.map((uri, index) => (
                  <View key={index} className="w-1/3 p-1">
                    <View className="relative">
                      <Image
                        source={{ uri }}
                        className="w-full aspect-square rounded-lg"
                      />
                      <TouchableOpacity
                        className="absolute top-2 right-2 bg-danger rounded-full w-8 h-8 items-center justify-center"
                        onPress={() => removePhoto(index)}
                      >
                        <Text className="text-white font-bold">✕</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ))}
              </View>
            </View>
          )}

          {photos.length === 0 && (
            <View className="bg-gray-50 rounded-xl p-8 items-center">
              <Text className="text-6xl mb-4">📸</Text>
              <Text className="text-gray-500 text-center">
                No photos yet. Take or select photos to continue.
              </Text>
            </View>
          )}
        </View>
      </ScrollView>

      <View className="p-6 border-t border-gray-100">
        <TouchableOpacity
          className={`bg-primary rounded-xl py-4 items-center ${photos.length === 0 ? 'opacity-50' : ''}`}
          onPress={handleContinue}
          disabled={photos.length === 0}
        >
          <Text className="text-white text-lg font-semibold">Continue</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
