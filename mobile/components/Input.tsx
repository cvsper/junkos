import { View, Text, TextInput, TextInputProps } from 'react-native';

interface InputProps extends TextInputProps {
  label?: string;
  error?: string;
}

export default function Input({ label, error, className = '', ...props }: InputProps) {
  return (
    <View>
      {label && (
        <Text className="text-sm font-medium text-gray-700 mb-2">{label}</Text>
      )}
      <TextInput
        className={`bg-gray-50 border rounded-xl px-4 py-4 text-base ${
          error ? 'border-danger' : 'border-gray-200'
        } ${className}`}
        placeholderTextColor="#8E8E93"
        {...props}
      />
      {error && (
        <Text className="text-sm text-danger mt-1">{error}</Text>
      )}
    </View>
  );
}
