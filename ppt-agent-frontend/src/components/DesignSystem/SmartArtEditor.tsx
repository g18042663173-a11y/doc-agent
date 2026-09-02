import { Button, Card, Form, Input, Select, Space } from 'antd';
import { useEffect, useState } from 'react';
import { apiClient } from '@/services/api';

export default function SmartArtEditor() {
  const [types, setTypes] = useState<string[]>([]);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    apiClient.getSmartArtTypes().then((data) => setTypes(data.types)).catch(() => undefined);
  }, []);

  const generate = async (values: { smartart_type: string; nodes: string }) => {
    const nodes = values.nodes
      .split('\n')
      .map((line, index) => line.trim())
      .filter(Boolean)
      .map((text, index) => ({ id: `n${index + 1}`, text, level: 0 }));
    const data = await apiClient.generateSmartArt({
      nodes,
      config: { smartart_type: values.smartart_type }
    });
    setResult(data.smartart);
  };

  return (
    <Space orientation="vertical" size={16} className="wide">
      <Card size="small">
        <Form layout="vertical" onFinish={generate} initialValues={{ smartart_type: 'process', nodes: '调研\n规划\n生成\n交付' }}>
          <Form.Item name="smartart_type" label="类型">
            <Select options={types.map((type) => ({ value: type, label: type }))} />
          </Form.Item>
          <Form.Item name="nodes" label="节点">
            <Input.TextArea rows={6} />
          </Form.Item>
          <Button type="primary" htmlType="submit" data-testid="smartart-generate">生成</Button>
        </Form>
      </Card>
      {result && <pre className="json-panel">{JSON.stringify(result, null, 2)}</pre>}
    </Space>
  );
}
