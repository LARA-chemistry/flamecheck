<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <router-view />
  </n-config-provider>
</template>

<script setup>
import { NConfigProvider } from 'naive-ui'

// Align Naive UI's primary accent with the Flame palette so buttons, tags and
// other components pick up the flame-orange identity automatically.
const themeOverrides = {
  common: {
    primaryColor: '#FF8A00',
    primaryColorHover: '#FFA033',
    primaryColorPressed: '#E57600',
    primaryColorSuppl: '#FF8A00',
    successColor: '#2E7D32',
    warningColor: '#F9A825',
    errorColor: '#E53935',
    infoColor: '#1976D2',
    borderRadius: '12px',
    fontFamily:
      "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  },
  Button: {
    borderRadiusMedium: '10px',
    borderRadiusLarge: '12px',
  },
  Card: {
    borderRadius: '16px',
  },
}
</script>
