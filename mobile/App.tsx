import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { StatusBar } from 'expo-status-bar';
import { Home, BarChart3, Zap, Trophy, LayoutGrid, Activity, CreditCard, User } from 'lucide-react-native';

import { THEME } from './src/constants/theme';
import { HomeScreen } from './src/screens/Home';
import { ProjectionsScreen } from './src/screens/Projections';
import { OptimizerScreen } from './src/screens/Optimizer';
import { SportsScreen } from './src/screens/Sports';
import { PerformanceScreen } from './src/screens/Performance';
import { DataSourceBadge } from './src/components/DataSourceBadge';

const Tab = createBottomTabNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <StatusBar style="light" />
      <Tab.Navigator
        screenOptions={({ route }) => ({
          headerShown: false,
          tabBarStyle: {
            backgroundColor: THEME.colors.background,
            borderTopColor: 'rgba(255,255,255,0.05)',
            height: 90,
            paddingBottom: 30,
            paddingTop: 10,
          },
          tabBarActiveTintColor: THEME.colors.primary,
          tabBarInactiveTintColor: THEME.colors.textSecondary,
          tabBarLabelStyle: {
            fontSize: 10,
            fontWeight: 'bold',
            marginTop: 4,
          },
          tabBarIcon: ({ color, size, focused }) => {
            if (route.name === 'Home') return <Home size={size} color={color} fill={focused ? color : 'transparent'} />;
            if (route.name === 'Projections') return <BarChart3 size={size} color={color} />;
            if (route.name === 'Optimizer') return <Zap size={size} color={color} fill={focused ? color : 'transparent'} />;
            if (route.name === 'Sports') return <Trophy size={size} color={color} />;
            if (route.name === 'Performance') return <Activity size={size} color={color} />;
            return null;
          },
        })}
      >
        <Tab.Screen name="Home" component={HomeScreen} />
        <Tab.Screen name="Projections" component={ProjectionsScreen} />
        <Tab.Screen name="Optimizer" component={OptimizerScreen} />
        <Tab.Screen name="Sports" component={SportsScreen} />
        <Tab.Screen name="Performance" component={PerformanceScreen} />
      </Tab.Navigator>
      <DataSourceBadge />
    </NavigationContainer>
  );
}
