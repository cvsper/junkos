import AsyncStorage from '@react-native-async-storage/async-storage';

export interface BookingData {
  address?: string;
  photos?: string[];
  serviceType?: string;
  serviceDetails?: string;
  scheduledDate?: string;
  scheduledTime?: string;
}

const BOOKING_DRAFT_KEY = 'booking_draft';

export const storage = {
  async getBookingDraft(): Promise<BookingData> {
    try {
      const draft = await AsyncStorage.getItem(BOOKING_DRAFT_KEY);
      return draft ? JSON.parse(draft) : {};
    } catch {
      return {};
    }
  },

  async saveBookingDraft(data: BookingData) {
    try {
      const existing = await this.getBookingDraft();
      const updated = { ...existing, ...data };
      await AsyncStorage.setItem(BOOKING_DRAFT_KEY, JSON.stringify(updated));
    } catch (error) {
      console.error('Failed to save booking draft:', error);
    }
  },

  async clearBookingDraft() {
    try {
      await AsyncStorage.removeItem(BOOKING_DRAFT_KEY);
    } catch (error) {
      console.error('Failed to clear booking draft:', error);
    }
  },

  async isAuthenticated(): Promise<boolean> {
    const token = await AsyncStorage.getItem('auth_token');
    return !!token;
  },
};
