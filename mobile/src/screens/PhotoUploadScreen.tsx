import React, { useState } from 'react';
import { View, StyleSheet, ScrollView, Image, TouchableOpacity, Alert } from 'react-native';
import { Button, Text, ActivityIndicator, IconButton } from 'react-native-paper';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as ImagePicker from 'expo-image-picker';
import { Camera } from 'expo-camera';
import { colors } from '../theme';
import { RootStackParamList } from '../types';
import { bookingsApi } from '../api/bookings';

type Props = NativeStackScreenProps<RootStackParamList, 'PhotoUpload'>;

export default function PhotoUploadScreen({ navigation, route }: Props) {
  const { address } = route.params;
  const [photos, setPhotos] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);

  const requestPermissions = async () => {
    const cameraPermission = await Camera.requestCameraPermissionsAsync();
    const libraryPermission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    
    return cameraPermission.status === 'granted' && libraryPermission.status === 'granted';
  };

  const takePhoto = async () => {
    const hasPermission = await requestPermissions();
    if (!hasPermission) {
      Alert.alert('Permission Required', 'Camera access is needed to take photos');
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [4, 3],
      quality: 0.8,
    });

    if (!result.canceled && result.assets[0]) {
      await uploadPhoto(result.assets[0].uri);
    }
  };

  const pickFromGallery = async () => {
    const hasPermission = await requestPermissions();
    if (!hasPermission) {
      Alert.alert('Permission Required', 'Photo library access is needed');
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsMultipleSelection: true,
      quality: 0.8,
    });

    if (!result.canceled) {
      for (const asset of result.assets) {
        await uploadPhoto(asset.uri);
      }
    }
  };

  const uploadPhoto = async (uri: string) => {
    setUploading(true);
    try {
      const fileName = uri.split('/').pop();
      const match = /\.(\w+)$/.exec(fileName || '');
      const type = match ? `image/${match[1]}` : 'image/jpeg';

      const response = await bookingsApi.uploadPhoto({
        uri,
        type,
        fileName: fileName || 'photo.jpg',
      });

      setPhotos([...photos, response.url]);
    } catch (error) {
      console.error('Upload error:', error);
      Alert.alert('Upload Failed', 'Failed to upload photo. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const removePhoto = (index: number) => {
    setPhotos(photos.filter((_, i) => i !== index));
  };

  const handleContinue = () => {
    if (photos.length === 0) {
      Alert.alert('No Photos', 'Please add at least one photo of the items', [
        { text: 'Skip', onPress: () => navigation.navigate('ItemSelection', { address, photos: [] }) },
        { text: 'Add Photo', style: 'cancel' },
      ]);
      return;
    }

    navigation.navigate('ItemSelection', { address, photos });
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Text style={styles.title}>Show us what you've got</Text>
          <Text style={styles.subtitle}>
            Photos help us provide accurate pricing and prepare for pickup
          </Text>
        </View>

        <View style={styles.buttonRow}>
          <Button
            mode="contained"
            onPress={takePhoto}
            style={styles.actionButton}
            icon="camera"
            labelStyle={styles.actionButtonLabel}
          >
            Take Photo
          </Button>
          <Button
            mode="outlined"
            onPress={pickFromGallery}
            style={styles.actionButton}
            icon="image"
            labelStyle={styles.actionButtonLabelOutlined}
          >
            From Gallery
          </Button>
        </View>

        {uploading && (
          <View style={styles.uploadingContainer}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.uploadingText}>Uploading...</Text>
          </View>
        )}

        {photos.length > 0 && (
          <View style={styles.photosContainer}>
            <Text style={styles.photosTitle}>Photos ({photos.length})</Text>
            <View style={styles.photosGrid}>
              {photos.map((photo, index) => (
                <View key={index} style={styles.photoWrapper}>
                  <Image source={{ uri: photo }} style={styles.photo} />
                  <IconButton
                    icon="close-circle"
                    size={24}
                    iconColor={colors.error}
                    style={styles.removeButton}
                    onPress={() => removePhoto(index)}
                  />
                </View>
              ))}
            </View>
          </View>
        )}

        <View style={styles.tips}>
          <Text style={styles.tipsTitle}>📸 Photo Tips:</Text>
          <Text style={styles.tipText}>• Take clear, well-lit photos</Text>
          <Text style={styles.tipText}>• Show items from multiple angles</Text>
          <Text style={styles.tipText}>• Include large items and bulky furniture</Text>
          <Text style={styles.tipText}>• Show the quantity if multiple items</Text>
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <Button
          mode="contained"
          onPress={handleContinue}
          style={styles.continueButton}
          labelStyle={styles.continueButtonLabel}
          contentStyle={styles.buttonContent}
          disabled={uploading}
        >
          Continue
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
    lineHeight: 24,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 24,
  },
  actionButton: {
    flex: 1,
    borderRadius: 12,
  },
  actionButtonLabel: {
    fontSize: 14,
    fontFamily: 'Poppins-Medium',
  },
  actionButtonLabelOutlined: {
    fontSize: 14,
    fontFamily: 'Poppins-Medium',
    color: colors.primary,
  },
  uploadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
    backgroundColor: colors.white,
    borderRadius: 12,
    marginBottom: 24,
  },
  uploadingText: {
    marginLeft: 12,
    fontSize: 16,
    fontFamily: 'OpenSans-Regular',
    color: colors.text,
  },
  photosContainer: {
    marginBottom: 24,
  },
  photosTitle: {
    fontSize: 18,
    fontFamily: 'Poppins-SemiBold',
    color: colors.text,
    marginBottom: 16,
  },
  photosGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  photoWrapper: {
    position: 'relative',
    width: '47%',
    aspectRatio: 1,
  },
  photo: {
    width: '100%',
    height: '100%',
    borderRadius: 12,
  },
  removeButton: {
    position: 'absolute',
    top: -8,
    right: -8,
    backgroundColor: colors.white,
    margin: 0,
  },
  tips: {
    backgroundColor: colors.white,
    padding: 20,
    borderRadius: 12,
    borderLeftWidth: 4,
    borderLeftColor: colors.info,
  },
  tipsTitle: {
    fontSize: 16,
    fontFamily: 'Poppins-SemiBold',
    color: colors.text,
    marginBottom: 12,
  },
  tipText: {
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
