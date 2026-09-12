import { App, Button, Card, Form, Input, Select, Space } from 'antd';
import { apiClient } from '@/services/api';

export default function NGAConfigForm({ onSaved }: { onSaved?: () => void }) {
  const { message } = App.useApp();
  const [form] = Form.useForm();

  const test = async () => {
    const values = form.getFieldsValue();
    const result = await apiClient.testConnection(values.nga_endpoint, values.auth_token);
    message[result.success ? 'success' : 'error'](result.message);
  };

  const save = async (values: Record<string, string>) => {
    await apiClient.createUser({
      user_name: values.user_name,
      nga_endpoint: values.nga_endpoint,
      auth_token: values.auth_token || 'EMPTY',
      llm_provider: values.llm_provider || 'nga',
      llm_model: values.llm_model || 'glm-4.7',
      ppt_renderer: 'stub'
    });
    message.success('模型配置档案已保存');
    form.resetFields();
    onSaved?.();
  };

  return (
    <Card size="small" title="模型配置档案">
      <Form form={form} layout="vertical" onFinish={save} initialValues={{ llm_provider: 'nga', llm_model: 'glm-4.7' }}>
        <Form.Item name="user_name" label="档案名称" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item name="llm_provider" label="Provider" rules={[{ required: true }]}>
          <Select
            options={[
              { label: 'NGA / GLM-4.7', value: 'nga' },
              { label: '本地中转站 local_relay', value: 'local_relay' },
              { label: 'OpenAI-compatible', value: 'openai_compatible' },
              { label: '本地 stub', value: 'stub' }
            ]}
          />
        </Form.Item>
        <Form.Item name="nga_endpoint" label="Endpoint" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item name="auth_token" label="Token"><Input.Password placeholder="无鉴权时填 EMPTY 或留空" /></Form.Item>
        <Form.Item name="llm_model" label="模型"><Input /></Form.Item>
        <Space>
          <Button onClick={test} data-testid="user-test-connection">测试连接</Button>
          <Button type="primary" htmlType="submit" data-testid="user-save">保存档案</Button>
        </Space>
      </Form>
    </Card>
  );
}
