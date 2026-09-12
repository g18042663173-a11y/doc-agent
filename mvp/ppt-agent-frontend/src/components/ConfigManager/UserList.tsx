import { DeleteOutlined, SwapOutlined } from '@ant-design/icons';
import { App, Button, Space, Table, Tag } from 'antd';
import { useEffect, useState } from 'react';
import { apiClient } from '@/services/api';
import { useUserStore } from '@/store';
import type { UserConfig } from '@/types';

export default function UserList({ refreshToken = 0 }: { refreshToken?: number }) {
  const { message } = App.useApp();
  const [users, setUsers] = useState<UserConfig[]>([]);
  const setCurrentUser = useUserStore((state) => state.setCurrentUser);

  const load = async () => setUsers((await apiClient.getUsers()).users);

  useEffect(() => {
    load().catch(() => undefined);
  }, [refreshToken]);

  const switchUser = async (userId: string) => {
    const user = await apiClient.switchUser(userId);
    setCurrentUser(user);
    message.success('已使用该模型档案');
    await load();
  };

  const remove = async (userId: string) => {
    await apiClient.deleteUser(userId);
    await load();
  };

  return (
    <Table
      rowKey="user_id"
      dataSource={users}
      pagination={false}
      scroll={{ x: 860 }}
      columns={[
        { title: '档案名称', dataIndex: 'user_name', width: 140, ellipsis: true },
        {
          title: 'Provider',
          dataIndex: 'llm_provider',
          width: 130,
          render: (value) => <Tag color={value === 'local_relay' ? 'blue' : 'default'}>{value}</Tag>
        },
        { title: '模型', dataIndex: 'llm_model', width: 120, ellipsis: true },
        { title: 'Endpoint', dataIndex: 'nga_endpoint', width: 220, ellipsis: true },
        { title: 'Token', width: 120, render: (_, record) => <Tag>{record.auth_token}</Tag> },
        {
          title: '操作',
          width: 120,
          render: (_, record) => (
            <Space>
              <Button aria-label={`使用 ${record.user_name}`} icon={<SwapOutlined />} onClick={() => switchUser(record.user_id)} />
              <Button danger aria-label={`删除 ${record.user_name}`} icon={<DeleteOutlined />} onClick={() => remove(record.user_id)} />
            </Space>
          )
        }
      ]}
    />
  );
}
