import React, { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Provider as PaperProvider } from 'react-native-paper';
import { StatusBar } from 'expo-status-bar';
import { useFonts } from 'expo-font';
import * as SplashScreen from 'expo-splash-screen';
import { StripeProvider } from '@stripe/stripe-react-native';

import { AuthProvider } from './src/context/AuthContext';
import { theme } from './src/theme';
import WelcomeScreen from './src/screens/WelcomeScreen';
import LoginScreen from './src/screens/LoginScreen';
import AddressInputScreen from './src/screens/AddressInputScreen';
import PhotoUploadScreen from './src/screens/PhotoUploadScreen';
import ItemSelectionScreen from './src/screens/ItemSelectionScreen';
import DateTimePickerScreen from './src/screens/DateTimePickerScreen';
import PaymentScreen from './src/screens/PaymentScreen';
import ConfirmationScreen from './src/screens/ConfirmationScreen';

const Stack = createNativeStackNavigator();
const STRIPE_KEY = process.env.STRIPE_PUBLISHABLE_KEY || 'pk_test_placeholder';

SplashScreen.preventAutoHideAsync();

export default function App() {
  const [fontsLoaded] = useFonts({
    'Poppins-Regular': require('./assets/fonts/Poppins-Regular.ttf'),
    'Poppins-Medium': require('./assets/fonts/Poppins-Medium.ttf'),
    'Poppins-SemiBold': require('./assets/fonts/Poppins-SemiBold.ttf'),
    'Poppins-Bold': require('./assets/fonts/Poppins-Bold.ttf'),
    'OpenSans-Regular': require('./assets/fonts/OpenSans-Regular.ttf'),
    'OpenSans-SemiBold': require('./assets/fonts/OpenSans-SemiBold.ttf'),
  });

  useEffect(() => {
    if (fontsLoaded) {
      SplashScreen.hideAsync();
    }
  }, [fontsLoaded]);

  if (!fontsLoaded) {
    return null;
  }

  return (
    <StripeProvider publishableKey={STRIPE_KEY}>
      <AuthProvider>
        <PaperProvider theme={theme}>
          <NavigationContainer>
            <StatusBar style="auto" />
            <Stack.Navigator
              initialRouteName="Welcome"
              screenOptions={{
                headerStyle: {
                  backgroundColor: theme.colors.primary,
                },
                headerTintColor: '#fff',
                headerTitleStyle: {
                  fontFamily: 'Poppins-SemiBold',
                },
              }}
            >
              <Stack.Screen
                name="Welcome"
                component={WelcomeScreen}
                options={{ headerShown: false }}
              />
              <Stack.Screen
                name="Login"
                component={LoginScreen}
                options={{ title: 'Sign In' }}
              />
              <Stack.Screen
                name="AddressInput"
                component={AddressInputScreen}
                options={{ title: 'Pickup Location' }}
              />
              <Stack.Screen
                name="PhotoUpload"
                component={PhotoUploadScreen}
                options={{ title: 'Upload Photos' }}
              />
              <Stack.Screen
                name="ItemSelection"
                component={ItemSelectionScreen}
                options={{ title: 'What Needs Removing?' }}
              />
              <Stack.Screen
                name="DateTimePicker"
                component={DateTimePickerScreen}
                options={{ title: 'Choose Date & Time' }}
              />
              <Stack.Screen
                name="Payment"
                component={PaymentScreen}
                options={{ title: 'Payment' }}
              />
              <Stack.Screen
                name="Confirmation"
                component={ConfirmationScreen}
                options={{ headerShown: false }}
              />
            </Stack.Navigator>
          </NavigationContainer>
        </PaperProvider>
      </AuthProvider>
    </StripeProvider>
  );
}
