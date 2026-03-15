import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'io.qin.app',
  appName: 'Qin',
  webDir: 'dist',
  // 生产环境打包时，必须移除 server.url 以加载本地的 dist
  // 如果需要真机调试开发服务器，可以临时开启，但打出正式包前必须移除
  server: {
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
