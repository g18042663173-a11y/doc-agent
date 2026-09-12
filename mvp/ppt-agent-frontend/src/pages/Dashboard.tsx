import { ApiOutlined, BgColorsOutlined, FilePptOutlined, PlayCircleOutlined, SettingOutlined } from '@ant-design/icons';
import { App, Button, Card, Col, Row, Space, Statistic, Table, Tag, Typography } from 'antd';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import GenerationHistory from '@/components/DocumentGenerator/GenerationHistory';
import { apiClient, getApiErrorMessage } from '@/services/api';
import { downloadBlob } from '@/services/fileService';
import type { ColorScheme, GenerateTask, TemplateConfig, UserConfig } from '@/types';

export default function Dashboard() {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [users, setUsers] = useState<UserConfig[]>([]);
  const [templates, setTemplates] = useState<TemplateConfig[]>([]);
  const [colors, setColors] = useState<ColorScheme[]>([]);
  const [tasks, setTasks] = useState<GenerateTask[]>([]);
  const [health, setHealth] = useState('本地 stub');

  const load = async () => {
    const [userData, templateData, colorData, historyData, systemHealth] = await Promise.all([
      apiClient.getUsers(),
      apiClient.getTemplates(),
      apiClient.getColorSchemes(),
      apiClient.getGenerationHistory(8),
      apiClient.getSystemHealth()
    ]);
    setUsers(userData.users);
    setTemplates(templateData.templates);
    setColors(colorData.schemes);
    setTasks(historyData.tasks);
    setHealth(`${systemHealth.llm_provider} · ${systemHealth.ppt_renderer} · ${systemHealth.ppt_compliance_gate || 'warn'}`);
  };

  useEffect(() => {
    load()
      .catch(() => setHealth('offline'));
  }, []);

  const downloadTask = async (task: GenerateTask) => {
    try {
      const blob = await apiClient.downloadFile(task.task_id);
      const target = task.metadata?.target === 'docx' ? 'docx' : 'pptx';
      downloadBlob(blob, `generated-${task.task_id.slice(0, 8)}.${target}`);
    } catch (error) {
      message.error(getApiErrorMessage(error, '历史结果下载失败，请复用参数重新生成。'));
    }
  };

  return (
    <Space orientation="vertical" size={20} className="page-stack">
      <section className="workbench-hero">
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} lg={15}>
            <span className="workbench-kicker">LOCAL WORKBENCH</span>
            <Typography.Title className="workbench-title">个人文档生成工作台</Typography.Title>
            <Typography.Paragraph className="workbench-subtitle">
              上传文件，选择风格，生成可编辑 PPTX/DOCX。历史、模板和模型档案都留在本地。
            </Typography.Paragraph>
          </Col>
          <Col xs={24} lg={9}>
            <Space wrap className="hero-actions">
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={() => navigate('/generate/smart')}>开始生成</Button>
              <Button icon={<SettingOutlined />} onClick={() => navigate('/config/nga')}>配置模型档案</Button>
              <Button icon={<FilePptOutlined />} onClick={() => navigate('/design/templates')}>导入模板</Button>
            </Space>
          </Col>
        </Row>
      </section>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={6}><Card size="small" className="metric-card"><Statistic title="模型配置档案" value={users.length} prefix={<span className="metric-icon"><SettingOutlined /></span>} /></Card></Col>
        <Col xs={24} md={6}><Card size="small" className="metric-card"><Statistic title="模板" value={templates.length} prefix={<span className="metric-icon"><FilePptOutlined /></span>} /></Card></Col>
        <Col xs={24} md={6}><Card size="small" className="metric-card"><Statistic title="配色" value={colors.length} prefix={<span className="metric-icon"><BgColorsOutlined /></span>} /></Card></Col>
        <Col xs={24} md={6}><Card size="small" className="metric-card"><Statistic title="模型服务" value={health} prefix={<span className="metric-icon"><ApiOutlined /></span>} /></Card></Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={15}>
          <Card size="small" title="最近生成">
            <GenerationHistory compact showTitle={false} tasks={tasks} onRefresh={load} onDownload={downloadTask} onReuse={(task) => navigate('/generate/smart', { state: { task } })} />
          </Card>
        </Col>
        <Col xs={24} xl={9}>
          <Card size="small" title="模板库">
            <Space orientation="vertical" size={14} className="wide">
              <Table
                size="small"
                rowKey="template_id"
                dataSource={templates.slice(0, 6)}
                pagination={false}
                columns={[
                  { title: '名称', dataIndex: 'name' },
                  { title: '分类', dataIndex: 'category' },
                  { title: '来源', render: (_, record) => <Tag color={record.is_system ? 'blue' : 'green'}>{record.is_system ? 'system' : 'custom'}</Tag> }
                ]}
              />
              <div>
                <Typography.Text strong className="dashboard-subheading">常用配色</Typography.Text>
                <Space wrap className="palette-strip">
                  {colors.slice(0, 6).map((scheme) => (
                    <Tag key={scheme.scheme_id} className="palette-tag">
                      <span className="color-swatch mini" style={{ background: scheme.primary_color }} />
                      {scheme.name}
                    </Tag>
                  ))}
                </Space>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
