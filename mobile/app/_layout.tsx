import { Stack } from 'expo-router';
import { GestureHandlerRootView } from 'react-native-gesture-handler';

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <Stack
        screenOptions={{
          headerStyle: {
            backgroundColor: '#007AFF',
          },
          headerTintColor: '#fff',
          headerTitleStyle: {
            fontWeight: '600',
          },
        }}
      >
        <Stack.Screen 
          name="index" 
          options={{ 
            title: 'Welcome',
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="screens/address" 
          options={{ title: 'Service Address' }} 
        />
        <Stack.Screen 
          name="screens/photos" 
          options={{ title: 'Upload Photos' }} 
        />
        <Stack.Screen 
          name="screens/service" 
          options={{ title: 'Service Details' }} 
        />
        <Stack.Screen 
          name="screens/datetime" 
          options={{ title: 'Schedule Service' }} 
        />
        <Stack.Screen 
          name="screens/confirmation" 
          options={{ title: 'Confirmation' }} 
        />
      </Stack>
    </GestureHandlerRootView>
  );
}
