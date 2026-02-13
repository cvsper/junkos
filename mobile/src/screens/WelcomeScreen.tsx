import React from 'react';
import { View, StyleSheet, Image } from 'react-native';
import { Button, Text } from 'react-native-paper';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '../theme';
import { RootStackParamList } from '../types';

type Props = NativeStackScreenProps<RootStackParamList, 'Welcome'>;

export default function WelcomeScreen({ navigation }: Props) {
  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        <View style={styles.logoContainer}>
          <Text style={styles.logo}>🚛</Text>
          <Text style={styles.title}>Umuve</Text>
          <Text style={styles.subtitle}>
            Hauling made simple.
          </Text>
        </View>

        <View style={styles.features}>
          <FeatureItem icon="📸" text="Snap photos of your items" />
          <FeatureItem icon="📅" text="Choose your pickup time" />
          <FeatureItem icon="💳" text="Pay securely with Stripe" />
          <FeatureItem icon="✅" text="We haul it away" />
        </View>

        <View style={styles.buttonContainer}>
          <Button
            mode="contained"
            onPress={() => navigation.navigate('Login')}
            style={styles.ctaButton}
            labelStyle={styles.ctaButtonLabel}
            contentStyle={styles.buttonContent}
          >
            Get Started
          </Button>
          <Text style={styles.footerText}>
            Quick, easy, and eco-friendly hauling
          </Text>
        </View>
      </View>
    </SafeAreaView>
  );
}

const FeatureItem = ({ icon, text }: { icon: string; text: string }) => (
  <View style={styles.featureItem}>
    <Text style={styles.featureIcon}>{icon}</Text>
    <Text style={styles.featureText}>{text}</Text>
  </View>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    flex: 1,
    justifyContent: 'space-between',
    paddingHorizontal: 24,
    paddingVertical: 32,
  },
  logoContainer: {
    alignItems: 'center',
    marginTop: 60,
  },
  logo: {
    fontSize: 72,
    marginBottom: 16,
  },
  title: {
    fontSize: 48,
    fontFamily: 'Poppins-Bold',
    color: colors.primary,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 18,
    fontFamily: 'OpenSans-Regular',
    color: colors.muted,
    textAlign: 'center',
    lineHeight: 28,
  },
  features: {
    marginVertical: 40,
  },
  featureItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 24,
    paddingHorizontal: 16,
  },
  featureIcon: {
    fontSize: 32,
    marginRight: 16,
  },
  featureText: {
    fontSize: 16,
    fontFamily: 'OpenSans-Regular',
    color: colors.text,
    flex: 1,
  },
  buttonContainer: {
    alignItems: 'center',
  },
  ctaButton: {
    backgroundColor: colors.cta,
    borderRadius: 12,
    width: '100%',
  },
  ctaButtonLabel: {
    fontSize: 18,
    fontFamily: 'Poppins-SemiBold',
    color: colors.white,
  },
  buttonContent: {
    paddingVertical: 8,
  },
  footerText: {
    fontSize: 14,
    fontFamily: 'OpenSans-Regular',
    color: colors.muted,
    textAlign: 'center',
    marginTop: 16,
  },
});
