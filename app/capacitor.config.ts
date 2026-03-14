import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'io.qin.app',
  appName: 'Qin',
  webDir: 'dist',
  server: {
    url: 'http://10.0.2.2:5175/',
    cleartext: true,
  },
  android: {
    allowMixedContent: true,
  },
  plugins: {
    StatusBar: {
      overlaysWebView: false,
      style: 'DARK',
      backgroundColor: '#ffffff'
    }
  }
};

export default config;
