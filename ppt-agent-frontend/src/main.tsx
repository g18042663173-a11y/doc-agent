import React from 'react';
import ReactDOM from 'react-dom/client';
import { App as AntApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#0071e3',
          colorSuccess: '#2f8f5b',
          colorWarning: '#b4690e',
          colorText: '#1d1d1f',
          colorTextSecondary: '#6e6e73',
          colorBgLayout: '#f5f5f7',
          colorBgContainer: 'rgba(255, 255, 255, 0.88)',
          colorBorder: '#d2d2d7',
          borderRadius: 8,
          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Microsoft YaHei", Arial, sans-serif'
        },
        components: {
          Button: {
            borderRadius: 999,
            controlHeight: 36,
            fontWeight: 500
          },
          Card: {
            borderRadiusLG: 8,
            boxShadowTertiary: '0 18px 46px rgba(0, 0, 0, 0.06)'
          },
          Select: {
            borderRadius: 8
          }
        }
      }}
    >
      <AntApp>
        <App />
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>
);
