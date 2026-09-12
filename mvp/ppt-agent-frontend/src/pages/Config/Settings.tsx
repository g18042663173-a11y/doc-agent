import { Card, Descriptions, Space } from 'antd';
import { useEffect, useState } from 'react';
import ConfigImportExport from '@/components/ConfigManager/ConfigImportExport';
import { apiClient } from '@/services/api';
import type { SystemHealth } from '@/types';

export default function Settings() {
  const [health, setHealth] = useState<SystemHealth | null>(null);

  useEffect(() => {
    apiClient.getSystemHealth().then(setHealth).catch(() => undefined);
  }, []);

  return (
    <Space orientation="vertical" size={16} className="wide">
      <Card size="small">
        <Descriptions column={1} size="small">
          <Descriptions.Item label="API">{import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'}</Descriptions.Item>
          <Descriptions.Item label="模型插座">{health?.llm_provider || 'stub'}</Descriptions.Item>
          <Descriptions.Item label="渲染插座">{health?.ppt_renderer || 'stub'}</Descriptions.Item>
          <Descriptions.Item label="合规闸">{health?.ppt_compliance_gate || 'warn'}</Descriptions.Item>
          <Descriptions.Item label="预览导出">{health?.preview_export_available ? 'available' : 'not configured'}</Descriptions.Item>
          <Descriptions.Item label="Version">{health?.version || '0.1.0'}</Descriptions.Item>
          <Descriptions.Item label="Mode">个人本地工作台</Descriptions.Item>
        </Descriptions>
      </Card>
      <ConfigImportExport />
    </Space>
  );
}
