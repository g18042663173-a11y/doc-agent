import { UploadOutlined } from '@ant-design/icons';
import { Alert, App, Button, Card, Input, Select, Space, Table, Tag, Typography, Upload } from 'antd';
import { useEffect, useState } from 'react';
import { apiClient, getApiErrorMessage } from '@/services/api';
import type { TemplateConfig } from '@/types';

export default function TemplateGallery() {
  const { message } = App.useApp();
  const [templates, setTemplates] = useState<TemplateConfig[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [category, setCategory] = useState('business');

  const load = async () => setTemplates((await apiClient.getTemplates()).templates);

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  const submit = async () => {
    if (!file || !name) return;
    try {
      const result = await apiClient.importTemplate(file, name, category);
      setFile(null);
      setName('');
      const summary = result.style_summary;
      const detail = summary?.slide_size?.ratio ? `：${summary.slide_size.ratio}，${summary.master_count ?? 0} 个母版` : '';
      message.success(`已导入风格${detail}`);
      await load();
    } catch (error) {
      message.error(getApiErrorMessage(error, '模板导入失败，请选择有效的 PPTX 文件。'));
    }
  };

  return (
    <Space orientation="vertical" size={16} className="wide">
      <Card size="small">
        <Space orientation="vertical" size={12} className="wide">
          <Alert
            type="info"
            showIcon
            title="自定义 PPTX 模板用于提取尺寸、字体和主题色；复杂母版、动画和占位符不会完整复刻。"
          />
          <Space wrap>
            <Input placeholder="模板名称" value={name} onChange={(event) => setName(event.target.value)} />
            <Select
              value={category}
              style={{ width: 140 }}
              options={[
                { value: 'business', label: 'business' },
                { value: 'tech', label: 'tech' },
                { value: 'education', label: 'education' },
                { value: 'creative', label: 'creative' }
              ]}
              onChange={setCategory}
            />
            <Upload accept=".pptx" maxCount={1} beforeUpload={(next) => { setFile(next); return false; }} onRemove={() => setFile(null)}>
              <Button icon={<UploadOutlined />}>选择 PPTX</Button>
            </Upload>
            <Button type="primary" disabled={!file || !name} onClick={submit} data-testid="template-import">导入风格</Button>
          </Space>
        </Space>
      </Card>
      <Table
        rowKey="template_id"
        dataSource={templates}
        pagination={false}
        columns={[
          { title: '名称', dataIndex: 'name' },
          { title: '分类', dataIndex: 'category' },
          { title: '说明', dataIndex: 'description' },
          {
            title: '风格摘要',
            render: (_, record) => {
              const summary = record.style_summary;
              if (!summary) return <Typography.Text type="secondary">系统默认</Typography.Text>;
              return (
                <Typography.Text type="secondary">
                  {summary.slide_size?.ratio || '尺寸'} · {summary.master_count ?? 0} masters
                </Typography.Text>
              );
            }
          },
          { title: '来源', render: (_, record) => <Tag color={record.is_system ? 'blue' : 'green'}>{record.is_system ? 'system' : 'custom'}</Tag> }
        ]}
      />
    </Space>
  );
}
