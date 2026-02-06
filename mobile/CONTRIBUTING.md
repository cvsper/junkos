# Contributing to JunkOS Mobile

Guidelines for contributing to the mobile app codebase.

## 📝 Code Style

### TypeScript

- Use TypeScript for all new files
- Define interfaces for all data structures
- Avoid `any` type (use sparingly with `// eslint-disable-next-line`)
- Use strict mode

### React Native

- Functional components with hooks (no class components)
- Use `React.FC` or explicit types for props
- Organize imports: React → React Native → third-party → local
- Use destructuring for props

### Naming Conventions

- **Components**: PascalCase (`WelcomeScreen.tsx`)
- **Files**: PascalCase for components, camelCase for utilities
- **Variables**: camelCase
- **Constants**: UPPER_SNAKE_CASE
- **Interfaces**: PascalCase with descriptive names

### File Structure

```typescript
// Imports
import React, { useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { Button } from 'react-native-paper';

// Types
import { RootStackParamList } from '../types';
type Props = NativeStackScreenProps<RootStackParamList, 'ScreenName'>;

// Component
export default function ScreenName({ navigation }: Props) {
  // State
  const [loading, setLoading] = useState(false);

  // Handlers
  const handleAction = () => {
    // ...
  };

  // Render
  return (
    <View style={styles.container}>
      {/* JSX */}
    </View>
  );
}

// Styles
const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
});
```

## 🎨 Design System

Follow `DESIGN_SYSTEM.md` guidelines:

- Use colors from `src/theme.ts`
- Font families: Poppins (headings), Open Sans (body)
- Spacing: multiples of 8 (8, 16, 24, 32)
- Border radius: 8 or 12
- iOS Human Interface Guidelines compliance

## 🧪 Testing

### Before Committing

```bash
# Type checking
npm run type-check

# Linting
npm run lint

# Fix auto-fixable issues
npm run lint -- --fix
```

### Manual Testing

Test on:
- iOS Simulator (iPhone 15 Pro)
- Physical iPhone (if available)
- Different network conditions (slow 3G, offline)

## 📦 Pull Request Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Follow code style above
   - Update relevant documentation
   - Test thoroughly

3. **Commit Messages**
   ```
   feat: Add photo upload screen
   fix: Resolve camera permission issue
   docs: Update README with setup steps
   style: Format code with Prettier
   refactor: Simplify auth context
   ```

4. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

5. **PR Description Template**
   ```markdown
   ## Changes
   - Added X feature
   - Fixed Y bug
   
   ## Testing
   - Tested on iOS 17 simulator
   - Verified offline behavior
   
   ## Screenshots
   [Attach relevant screenshots]
   ```

## 🐛 Bug Reports

Use GitHub Issues with this template:

```markdown
**Description**
Clear description of the bug

**Steps to Reproduce**
1. Open app
2. Navigate to X
3. Tap Y
4. See error

**Expected Behavior**
What should happen

**Actual Behavior**
What actually happened

**Environment**
- iOS version: 17.2
- Device: iPhone 15 Pro
- App version: 1.0.0

**Screenshots**
[Attach if applicable]
```

## 🆕 Feature Requests

```markdown
**Feature Description**
What feature you want

**Use Case**
Why this feature is needed

**Proposed Implementation**
How it could work

**Alternatives Considered**
Other approaches
```

## 📚 Documentation

Update documentation when:
- Adding new screens
- Changing API endpoints
- Modifying environment variables
- Adding dependencies
- Changing build process

## 🔒 Security

- Never commit `.env` files
- Use environment variables for secrets
- Validate user input
- Sanitize data before API calls
- Report security issues privately

## 🎯 Priority Labels

- `P0: Critical` - Blocking issues, crashes
- `P1: High` - Major features, important bugs
- `P2: Medium` - Nice-to-haves, minor bugs
- `P3: Low` - Polish, future enhancements

## ✅ Review Checklist

Before requesting review:

- [ ] Code follows style guide
- [ ] TypeScript types defined
- [ ] No console.log statements
- [ ] Tested on iOS simulator
- [ ] Documentation updated
- [ ] No merge conflicts
- [ ] Descriptive commit messages
- [ ] PR description complete

## 📖 Resources

- [React Native Docs](https://reactnative.dev/docs/getting-started)
- [Expo Docs](https://docs.expo.dev/)
- [React Navigation](https://reactnavigation.org/)
- [iOS HIG](https://developer.apple.com/design/human-interface-guidelines/)

---

**Questions?** Open a discussion or ask in team chat.
