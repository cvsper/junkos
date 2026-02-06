import React, { useState, useEffect } from 'react';
import { View, StyleSheet, ScrollView, Alert, TouchableOpacity } from 'react-native';
import { Button, TextInput, Text, ActivityIndicator } from 'react-native-paper';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { SafeAreaView } from 'react-native-safe-area-context';
import MapView, { Marker, PROVIDER_APPLE } from 'react-native-maps';
import * as Location from 'expo-location';
import { colors } from '../theme';
import { RootStackParamList, Address } from '../types';

type Props = NativeStackScreenProps<RootStackParamList, 'AddressInput'>;

export default function AddressInputScreen({ navigation }: Props) {
  const [loading, setLoading] = useState(false);
  const [locationLoading, setLocationLoading] = useState(false);
  
  const [street, setStreet] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [zipCode, setZipCode] = useState('');
  const [location, setLocation] = useState({
    latitude: 37.78825,
    longitude: -122.4324,
  });

  useEffect(() => {
    requestLocationPermission();
  }, []);

  const requestLocationPermission = async () => {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status === 'granted') {
        getCurrentLocation();
      }
    } catch (error) {
      console.error('Error requesting location:', error);
    }
  };

  const getCurrentLocation = async () => {
    setLocationLoading(true);
    try {
      const currentLocation = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      
      setLocation({
        latitude: currentLocation.coords.latitude,
        longitude: currentLocation.coords.longitude,
      });

      // Reverse geocode to get address
      const addresses = await Location.reverseGeocodeAsync({
        latitude: currentLocation.coords.latitude,
        longitude: currentLocation.coords.longitude,
      });

      if (addresses[0]) {
        const addr = addresses[0];
        setStreet(`${addr.streetNumber || ''} ${addr.street || ''}`);
        setCity(addr.city || '');
        setState(addr.region || '');
        setZipCode(addr.postalCode || '');
      }
    } catch (error) {
      console.error('Error getting location:', error);
      Alert.alert('Error', 'Failed to get current location');
    } finally {
      setLocationLoading(false);
    }
  };

  const handleContinue = () => {
    if (!street || !city || !state || !zipCode) {
      Alert.alert('Error', 'Please fill in all address fields');
      return;
    }

    const address: Address = {
      street,
      city,
      state,
      zipCode,
      latitude: location.latitude,
      longitude: location.longitude,
    };

    navigation.navigate('PhotoUpload', { address });
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Text style={styles.title}>Where should we pick up?</Text>
          <Text style={styles.subtitle}>Enter your pickup location</Text>
        </View>

        <View style={styles.mapContainer}>
          <MapView
            provider={PROVIDER_APPLE}
            style={styles.map}
            region={{
              ...location,
              latitudeDelta: 0.01,
              longitudeDelta: 0.01,
            }}
            showsUserLocation
            showsMyLocationButton
          >
            <Marker coordinate={location} title="Pickup Location" />
          </MapView>
        </View>

        <TouchableOpacity
          onPress={getCurrentLocation}
          style={styles.locationButton}
          disabled={locationLoading}
        >
          {locationLoading ? (
            <ActivityIndicator color={colors.primary} />
          ) : (
            <Text style={styles.locationButtonText}>📍 Use Current Location</Text>
          )}
        </TouchableOpacity>

        <View style={styles.form}>
          <TextInput
            label="Street Address"
            value={street}
            onChangeText={setStreet}
            mode="outlined"
            style={styles.input}
            placeholder="123 Main St"
          />
          <TextInput
            label="City"
            value={city}
            onChangeText={setCity}
            mode="outlined"
            style={styles.input}
            placeholder="San Francisco"
          />
          <View style={styles.row}>
            <TextInput
              label="State"
              value={state}
              onChangeText={setState}
              mode="outlined"
              style={[styles.input, styles.stateInput]}
              placeholder="CA"
              autoCapitalize="characters"
              maxLength={2}
            />
            <TextInput
              label="ZIP Code"
              value={zipCode}
              onChangeText={setZipCode}
              mode="outlined"
              style={[styles.input, styles.zipInput]}
              placeholder="94105"
              keyboardType="number-pad"
              maxLength={5}
            />
          </View>

          <Button
            mode="contained"
            onPress={handleContinue}
            style={styles.continueButton}
            labelStyle={styles.continueButtonLabel}
            contentStyle={styles.buttonContent}
            disabled={loading}
          >
            Continue
          </Button>
        </View>
      </ScrollView>
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
    paddingVertical: 16,
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
  mapContainer: {
    height: 200,
    borderRadius: 12,
    overflow: 'hidden',
    marginBottom: 16,
  },
  map: {
    flex: 1,
  },
  locationButton: {
    backgroundColor: colors.white,
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginBottom: 24,
    borderWidth: 1,
    borderColor: colors.border,
  },
  locationButtonText: {
    fontSize: 16,
    fontFamily: 'Poppins-Medium',
    color: colors.primary,
  },
  form: {
    flex: 1,
  },
  input: {
    marginBottom: 16,
    backgroundColor: colors.white,
  },
  row: {
    flexDirection: 'row',
    gap: 12,
  },
  stateInput: {
    flex: 1,
  },
  zipInput: {
    flex: 1,
  },
  continueButton: {
    backgroundColor: colors.cta,
    borderRadius: 12,
    marginTop: 8,
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
