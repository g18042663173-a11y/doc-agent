import { App, Button, Card, Form, Input, Space, Table, Tag } from 'antd';
import { useEffect, useState } from 'react';
import { apiClient } from '@/services/api';
import type { ColorScheme } from '@/types';

export default function ColorPicker() {
  const { message } = App.useApp();
  const [schemes, setSchemes] = useState<ColorScheme[]>([]);
  const [scenario, setScenario] = useState('商务报告');
  const [recommendation, setRecommendation] = useState<string>('');
  const [form] = Form.useForm();

  const load = async () => setSchemes((await apiClient.getColorSchemes()).schemes);

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  const recommend = async () => {
    const data = await apiClient.recommendColors(scenario);
    setRecommendation(data.recommendations[0]?.scheme_id || '');
  };

  const create = async (values: Partial<ColorScheme>) => {
    await apiClient.createColorScheme(values);
    form.resetFields();
    message.success('已创建');
    await load();
  };

  return (
    <Space orientation="vertical" size={16} className="wide">
      <Card size="small">
        <Space wrap>
          <Input value={scenario} onChange={(event) => setScenario(event.target.value)} style={{ width: 220 }} />
          <Button onClick={recommend} data-testid="color-recommend">推荐</Button>
          {recommendation && <Tag color="blue" data-testid="color-recommendation">{recommendation}</Tag>}
        </Space>
      </Card>
      <Table
        rowKey="scheme_id"
        dataSource={schemes}
        pagination={false}
        columns={[
          { title: '名称', dataIndex: 'name' },
          { title: '分类', dataIndex: 'category' },
          {
            title: '色板',
            render: (_, record) => (
              <Space>
                {[record.primary_color, record.secondary_color, record.accent_color, record.background_color, record.text_color].map((color) => (
                  <span key={color} className="color-swatch" style={{ background: color }} />
                ))}
              </Space>
            )
          },
          { title: '来源', render: (_, record) => <Tag color={record.is_system ? 'blue' : 'green'}>{record.is_system ? 'system' : 'custom'}</Tag> }
        ]}
      />
      <Card size="small" title="自定义">
        <Form form={form} layout="inline" onFinish={create}>
          <Form.Item name="name" rules={[{ required: true }]}><Input placeholder="名称" /></Form.Item>
          <Form.Item name="category" rules={[{ required: true }]}><Input placeholder="分类" /></Form.Item>
          <Form.Item name="primary_color" rules={[{ required: true }]}><Input placeholder="#123456" /></Form.Item>
          <Form.Item name="secondary_color" rules={[{ required: true }]}><Input placeholder="#234567" /></Form.Item>
          <Form.Item name="accent_color" rules={[{ required: true }]}><Input placeholder="#345678" /></Form.Item>
          <Form.Item name="background_color" initialValue="#FFFFFF"><Input /></Form.Item>
          <Form.Item name="text_color" initialValue="#111111"><Input /></Form.Item>
          <Button htmlType="submit" type="primary" data-testid="color-save">保存</Button>
        </Form>
      </Card>
    </Space>
  );
}
