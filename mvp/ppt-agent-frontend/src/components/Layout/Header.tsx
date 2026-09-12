import { MenuFoldOutlined, MenuUnfoldOutlined, ReloadOutlined } from '@ant-design/icons';
import { Button, Layout, Select, Space, Tag } from 'antd';
import { useEffect } from 'react';
import { apiClient } from '@/services/api';
import { useTemplateStore, useUIStore, useUserStore } from '@/store';

const { Header } = Layout;

export default function AppHeader() {
  const collapsed = useUIStore((state) => state.collapsed);
  const setCollapsed = useUIStore((state) => state.setCollapsed);
  const users = useUserStore((state) => state.users);
  const currentUser = useUserStore((state) => state.currentUser);
  const setUsers = useUserStore((state) => state.setUsers);
  const setCurrentUser = useUserStore((state) => state.setCurrentUser);
  const setTemplates = useTemplateStore((state) => state.setTemplates);
  const setColorSchemes = useTemplateStore((state) => state.setColorSchemes);

  const refresh = async () => {
    const [userData, templateData, colorData] = await Promise.all([
      apiClient.getUsers(),
      apiClient.getTemplates(),
      apiClient.getColorSchemes()
    ]);
    setUsers(userData.users);
    setTemplates(templateData.templates);
    setColorSchemes(colorData.schemes);
  };

  useEffect(() => {
    refresh().catch(() => undefined);
  }, []);

  const switchUser = async (userId: string) => {
    const user = await apiClient.switchUser(userId);
    setCurrentUser(user);
    await refresh();
  };

  return (
    <Header className="app-header">
      <Space>
        <Button
          aria-label="切换导航"
          icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={() => setCollapsed(!collapsed)}
        />
        <Tag color="blue">{currentUser ? '模型档案' : 'Stub 默认'}</Tag>
      </Space>
      <Space>
        <Select
          value={currentUser?.user_id}
          placeholder="选择模型档案"
          style={{ minWidth: 180 }}
          options={users.map((user) => ({ value: user.user_id, label: user.user_name }))}
          onChange={switchUser}
          allowClear
          onClear={() => setCurrentUser(null)}
        />
        <Button aria-label="刷新" icon={<ReloadOutlined />} onClick={refresh} />
      </Space>
    </Header>
  );
}
