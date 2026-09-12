import { App as AntApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import type { ReactElement } from 'react';
import { render } from '@testing-library/react';

export function renderWithProviders(ui: ReactElement) {
  return render(
    <ConfigProvider locale={zhCN}>
      <AntApp>{ui}</AntApp>
    </ConfigProvider>
  );
}
