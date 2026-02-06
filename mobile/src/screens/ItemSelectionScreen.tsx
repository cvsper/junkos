import React, { useState } from 'react';
import { View, StyleSheet, ScrollView, Alert, TouchableOpacity } from 'react-native';
import { Button, TextInput, Text, Chip } from 'react-native-paper';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '../theme';
import { RootStackParamList, BookingItem } from '../types';

type Props = NativeStackScreenProps<RootStackParamList, 'ItemSelection'>;

const COMMON_ITEMS = [
  { name: 'Furniture', category: 'large', icon: '🛋️' },
  { name: 'Appliances', category: 'large', icon: '🧊' },
  { name: 'Mattress', category: 'large', icon: '🛏️' },
  { name: 'Electronics', category: 'medium', icon: '📺' },
  { name: 'Boxes', category: 'small', icon: '📦' },
  { name: 'Yard Waste', category: 'medium', icon: '🌿' },
  { name: 'Construction Debris', category: 'large', icon: '🏗️' },
  { name: 'E-Waste', category: 'small', icon: '💻' },
];

export default function ItemSelectionScreen({ navigation, route }: Props) {
  const { address, photos } = route.params;
  const [selectedItems, setSelectedItems] = useState<BookingItem[]>([]);
  const [customItem, setCustomItem] = useState('');
  const [description, setDescription] = useState('');

  const toggleItem = (item: { name: string; category: string }) => {
    const exists = selectedItems.find((i) => i.name === item.name);
    if (exists) {
      setSelectedItems(selectedItems.filter((i) => i.name !== item.name));
    } else {
      setSelectedItems([
        ...selectedItems,
        { name: item.name, category: item.category, quantity: 1 },
      ]);
    }
  };

  const updateQuantity = (name: string, delta: number) => {
    setSelectedItems(
      selectedItems.map((item) => {
        if (item.name === name) {
          const newQuantity = Math.max(1, item.quantity + delta);
          return { ...item, quantity: newQuantity };
        }
        return item;
      })
    );
  };

  const addCustomItem = () => {
    if (!customItem.trim()) {
      return;
    }

    const exists = selectedItems.find((i) => i.name === customItem);
    if (exists) {
      Alert.alert('Item Already Added', 'This item is already in your list');
      return;
    }

    setSelectedItems([
      ...selectedItems,
      { name: customItem, category: 'medium', quantity: 1 },
    ]);
    setCustomItem('');
  };

  const handleContinue = () => {
    if (selectedItems.length === 0) {
      Alert.alert('No Items Selected', 'Please select at least one item to remove');
      return;
    }

    const itemsWithDescription = selectedItems.map((item) => ({
      ...item,
      description: description || undefined,
    }));

    navigation.navigate('DateTimePicker', {
      address,
      photos,
      items: itemsWithDescription,
    });
  };

  const isSelected = (name: string) => selectedItems.some((i) => i.name === name);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Text style={styles.title}>What needs to go?</Text>
          <Text style={styles.subtitle}>Select all items you need removed</Text>
        </View>

        <View style={styles.itemsGrid}>
          {COMMON_ITEMS.map((item) => (
            <TouchableOpacity
              key={item.name}
              style={[styles.itemCard, isSelected(item.name) && styles.itemCardSelected]}
              onPress={() => toggleItem(item)}
            >
              <Text style={styles.itemIcon}>{item.icon}</Text>
              <Text style={styles.itemName}>{item.name}</Text>
              {isSelected(item.name) && (
                <View style={styles.quantityControls}>
                  <TouchableOpacity
                    style={styles.quantityButton}
                    onPress={() => updateQuantity(item.name, -1)}
                  >
                    <Text style={styles.quantityButtonText}>−</Text>
                  </TouchableOpacity>
                  <Text style={styles.quantity}>
                    {selectedItems.find((i) => i.name === item.name)?.quantity}
                  </Text>
                  <TouchableOpacity
                    style={styles.quantityButton}
                    onPress={() => updateQuantity(item.name, 1)}
                  >
                    <Text style={styles.quantityButtonText}>+</Text>
                  </TouchableOpacity>
                </View>
              )}
            </TouchableOpacity>
          ))}
        </View>

        <View style={styles.customSection}>
          <Text style={styles.sectionTitle}>Add Custom Item</Text>
          <View style={styles.customInputRow}>
            <TextInput
              value={customItem}
              onChangeText={setCustomItem}
              mode="outlined"
              style={styles.customInput}
              placeholder="e.g., Old carpet"
              onSubmitEditing={addCustomItem}
            />
            <Button
              mode="contained"
              onPress={addCustomItem}
              style={styles.addButton}
              compact
            >
              Add
            </Button>
          </View>
        </View>

        {selectedItems.length > 0 && (
          <View style={styles.selectedSection}>
            <Text style={styles.sectionTitle}>Selected Items ({selectedItems.length})</Text>
            <View style={styles.chipContainer}>
              {selectedItems.map((item) => (
                <Chip
                  key={item.name}
                  onClose={() => toggleItem(item)}
                  style={styles.chip}
                >
                  {item.name} × {item.quantity}
                </Chip>
              ))}
            </View>
          </View>
        )}

        <View style={styles.descriptionSection}>
          <Text style={styles.sectionTitle}>Additional Details (Optional)</Text>
          <TextInput
            value={description}
            onChangeText={setDescription}
            mode="outlined"
            style={styles.descriptionInput}
            placeholder="Any special instructions or details about the items..."
            multiline
            numberOfLines={4}
          />
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <Button
          mode="contained"
          onPress={handleContinue}
          style={styles.continueButton}
          labelStyle={styles.continueButtonLabel}
          contentStyle={styles.buttonContent}
          disabled={selectedItems.length === 0}
        >
          Continue to Date & Time
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
  itemsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 24,
  },
  itemCard: {
    width: '47%',
    backgroundColor: colors.white,
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: 'transparent',
  },
  itemCardSelected: {
    borderColor: colors.primary,
    backgroundColor: '#EEF2FF',
  },
  itemIcon: {
    fontSize: 32,
    marginBottom: 8,
  },
  itemName: {
    fontSize: 14,
    fontFamily: 'Poppins-Medium',
    color: colors.text,
    textAlign: 'center',
  },
  quantityControls: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 12,
    gap: 8,
  },
  quantityButton: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  quantityButtonText: {
    color: colors.white,
    fontSize: 18,
    fontFamily: 'Poppins-SemiBold',
  },
  quantity: {
    fontSize: 16,
    fontFamily: 'Poppins-SemiBold',
    color: colors.text,
    minWidth: 24,
    textAlign: 'center',
  },
  customSection: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 16,
    fontFamily: 'Poppins-SemiBold',
    color: colors.text,
    marginBottom: 12,
  },
  customInputRow: {
    flexDirection: 'row',
    gap: 12,
    alignItems: 'center',
  },
  customInput: {
    flex: 1,
    backgroundColor: colors.white,
  },
  addButton: {
    borderRadius: 8,
  },
  selectedSection: {
    marginBottom: 24,
  },
  chipContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    backgroundColor: colors.white,
  },
  descriptionSection: {
    marginBottom: 24,
  },
  descriptionInput: {
    backgroundColor: colors.white,
    minHeight: 100,
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
