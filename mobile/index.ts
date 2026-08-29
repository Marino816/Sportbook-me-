/**
 * LEGACY / UNUSED.
 * Expo does not load this file. The live entry is `expo-router/entry` → `mobile/app/_layout.tsx`.
 */
import { registerRootComponent } from 'expo';

import App from './App';

// registerRootComponent calls AppRegistry.registerComponent('main', () => App);
// It also ensures that whether you load the app in Expo Go or in a native build,
// the environment is set up appropriately
registerRootComponent(App);
