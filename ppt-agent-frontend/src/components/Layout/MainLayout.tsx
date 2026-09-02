import { Layout } from 'antd';
import { Outlet } from 'react-router-dom';
import AppHeader from './Header';
import Sidebar from './Sidebar';
import { useUIStore } from '@/store';

const { Content } = Layout;

export default function MainLayout() {
  const collapsed = useUIStore((state) => state.collapsed);

  return (
    <Layout className="app-shell">
      <Sidebar />
      <Layout className={collapsed ? 'app-main collapsed' : 'app-main'}>
        <AppHeader />
        <Content className="app-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
