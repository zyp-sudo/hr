import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import '@xyflow/react/dist/style.css';
import './styles.css';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#3b82f6',
          colorBgBase: '#060b16',
          colorBgContainer: '#0b1220',
          colorBorder: '#1d2b44',
          colorText: '#e5eefb',
          borderRadius: 8
        }
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>
);
