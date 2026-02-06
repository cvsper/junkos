import { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Alert, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { storage } from '../../utils/storage';

const TIME_SLOTS = [
  '8:00 AM - 10:00 AM',
  '10:00 AM - 12:00 PM',
  '12:00 PM - 2:00 PM',
  '2:00 PM - 4:00 PM',
  '4:00 PM - 6:00 PM',
];

export default function DateTimeScreen() {
  const router = useRouter();
  const [selectedDate, setSelectedDate] = useState('');
  const [selectedTime, setSelectedTime] = useState('');
  const [availableDates, setAvailableDates] = useState<string[]>([]);

  useEffect(() => {
    generateAvailableDates();
    loadDraft();
  }, []);

  const generateAvailableDates = () => {
    const dates: string[] = [];
    const today = new Date();
    
    // Generate next 7 days (excluding Sundays for example)
    for (let i = 1; i <= 10; i++) {
      const date = new Date(today);
      date.setDate(today.getDate() + i);
      
      if (date.getDay() !== 0) { // Skip Sundays
        dates.push(date.toISOString().split('T')[0]);
      }
      
      if (dates.length === 7) break;
    }
    
    setAvailableDates(dates);
  };

  const loadDraft = async () => {
    const draft = await storage.getBookingDraft();
    if (draft.scheduledDate) setSelectedDate(draft.scheduledDate);
    if (draft.scheduledTime) setSelectedTime(draft.scheduledTime);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString + 'T00:00:00');
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    
    return {
      dayOfWeek: days[date.getDay()],
      month: months[date.getMonth()],
      day: date.getDate(),
    };
  };

  const handleContinue = async () => {
    if (!selectedDate || !selectedTime) {
      Alert.alert('Selection Required', 'Please select both date and time');
      return;
    }

    await storage.saveBookingDraft({
      scheduledDate: selectedDate,
      scheduledTime: selectedTime,
    });

    router.push('/screens/confirmation');
  };

  return (
    <View className="flex-1 bg-white">
      <ScrollView className="flex-1">
        <View className="p-6">
          <Text className="text-2xl font-bold text-gray-900 mb-2">
            When should we come?
          </Text>
          <Text className="text-base text-gray-500 mb-6">
            Select your preferred date and time
          </Text>

          <View className="mb-6">
            <Text className="text-sm font-medium text-gray-700 mb-3">Select Date</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View className="flex-row space-x-3">
                {availableDates.map((date) => {
                  const formatted = formatDate(date);
                  const isSelected = selectedDate === date;
                  
                  return (
                    <TouchableOpacity
                      key={date}
                      className={`rounded-xl p-4 border-2 min-w-[80px] items-center ${
                        isSelected
                          ? 'border-primary bg-blue-50'
                          : 'border-gray-200 bg-white'
                      }`}
                      onPress={() => setSelectedDate(date)}
                    >
                      <Text
                        className={`text-xs font-medium mb-1 ${
                          isSelected ? 'text-primary' : 'text-gray-500'
                        }`}
                      >
                        {formatted.dayOfWeek}
                      </Text>
                      <Text
                        className={`text-2xl font-bold ${
                          isSelected ? 'text-primary' : 'text-gray-900'
                        }`}
                      >
                        {formatted.day}
                      </Text>
                      <Text
                        className={`text-xs ${
                          isSelected ? 'text-primary' : 'text-gray-500'
                        }`}
                      >
                        {formatted.month}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </ScrollView>
          </View>

          <View>
            <Text className="text-sm font-medium text-gray-700 mb-3">Select Time</Text>
            <View className="space-y-3">
              {TIME_SLOTS.map((time) => {
                const isSelected = selectedTime === time;
                
                return (
                  <TouchableOpacity
                    key={time}
                    className={`rounded-xl p-4 border-2 ${
                      isSelected
                        ? 'border-primary bg-blue-50'
                        : 'border-gray-200 bg-white'
                    }`}
                    onPress={() => setSelectedTime(time)}
                  >
                    <Text
                      className={`text-base font-semibold ${
                        isSelected ? 'text-primary' : 'text-gray-900'
                      }`}
                    >
                      {time}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          <View className="mt-6 bg-blue-50 rounded-xl p-4">
            <Text className="text-sm text-gray-700">
              💡 <Text className="font-semibold">Tip:</Text> Our crew will arrive during the selected time window. 
              Most jobs take 1-2 hours depending on volume.
            </Text>
          </View>
        </View>
      </ScrollView>

      <View className="p-6 border-t border-gray-100">
        <TouchableOpacity
          className={`bg-primary rounded-xl py-4 items-center ${
            !selectedDate || !selectedTime ? 'opacity-50' : ''
          }`}
          onPress={handleContinue}
          disabled={!selectedDate || !selectedTime}
        >
          <Text className="text-white text-lg font-semibold">Continue</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
