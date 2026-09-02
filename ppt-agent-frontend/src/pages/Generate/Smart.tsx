import { App, Card, Col, Row, Space, Tag, Typography } from 'antd';
import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import FileUpload from '@/components/DocumentGenerator/FileUpload';
import GenerateForm from '@/components/DocumentGenerator/GenerateForm';
import GenerationHistory from '@/components/DocumentGenerator/GenerationHistory';
import ProgressBar from '@/components/DocumentGenerator/ProgressBar';
import ResultPreview from '@/components/DocumentGenerator/ResultPreview';
import { apiClient, getApiErrorMessage } from '@/services/api';
import { downloadBlob } from '@/services/fileService';
import { connectProgressSocket } from '@/services/websocket';
import { useDocumentStore, useTemplateStore, useUserStore } from '@/store';
import type { ColorScheme, GenerateTask, ProgressResponse, SystemHealth, TargetType, TemplateConfig, UserConfig } from '@/types';

const terminalStatuses = new Set(['completed', 'failed', 'not_found']);

export default function SmartGenerate() {
  const { message } = App.useApp();
  const location = useLocation();
  const [file, setFile] = useState<File | null>(null);
  const [target, setTarget] = useState<TargetType>('pptx');
  const [slides, setSlides] = useState(8);
  const [templateId, setTemplateId] = useState<string | undefined>();
  const [colorSchemeId, setColorSchemeId] = useState<string | undefined>();
  const [userId, setUserId] = useState<string | undefined>();
  const [loading, setLoading] = useState(false);
  const [templates, setTemplates] = useState<TemplateConfig[]>([]);
  const [colors, setColors] = useState<ColorScheme[]>([]);
  const [users, setUsers] = useState<UserConfig[]>([]);
  const [history, setHistory] = useState<GenerateTask[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const progress = useDocumentStore((state) => state.progress);
  const setProgress = useDocumentStore((state) => state.setProgress);
  const setTaskId = useDocumentStore((state) => state.setTaskId);
  const setTemplateStore = useTemplateStore((state) => state.setTemplates);
  const setColorStore = useTemplateStore((state) => state.setColorSchemes);
  const setUserStore = useUserStore((state) => state.setUsers);
  const socketRef = useRef<WebSocket | null>(null);

  const applyTaskParameters = (task: GenerateTask) => {
    if (task.metadata?.target === 'pptx' || task.metadata?.target === 'docx') setTarget(task.metadata.target);
    if (task.metadata?.slides) setSlides(task.metadata.slides);
    setTemplateId(task.metadata?.template_id || undefined);
    setColorSchemeId(task.metadata?.color_scheme_id || undefined);
    setUserId(task.metadata?.user_id || undefined);
  };

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      setHistory((await apiClient.getGenerationHistory(12)).tasks);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    Promise.all([
      apiClient.getTemplates(),
      apiClient.getColorSchemes(),
      apiClient.getUsers(),
      apiClient.getGenerationHistory(12),
      apiClient.getSystemHealth()
    ]).then(([t, c, u, h, health]) => {
      setTemplates(t.templates);
      setColors(c.schemes);
      setUsers(u.users);
      setHistory(h.tasks);
      setSystemHealth(health);
      setTemplateStore(t.templates);
      setColorStore(c.schemes);
      setUserStore(u.users);
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    const task = (location.state as { task?: GenerateTask } | null)?.task;
    if (!task) return;
    applyTaskParameters(task);
    message.info('已复用参数，请重新选择输入文件后生成');
  }, [location.state]);

  useEffect(() => {
    return () => {
      socketRef.current?.close();
    };
  }, []);

  const poll = async (taskId: string) => {
    const next = await apiClient.getProgress(taskId);
    setProgress(next);
    if (!terminalStatuses.has(next.status)) {
      window.setTimeout(() => poll(taskId).catch(() => undefined), 1000);
    } else {
      setLoading(false);
      loadHistory().catch(() => undefined);
    }
  };

  const start = async () => {
    if (!file) {
      message.error('请选择文件');
      return;
    }
    setLoading(true);
    try {
      const response = await apiClient.startGeneration(file, {
        target,
        slides,
        template_id: templateId,
        color_scheme_id: colorSchemeId,
        user_id: userId
      });
      setTaskId(response.task_id);
      setProgress({ task_id: response.task_id, status: response.status, progress: 0, current_step: response.message });
      socketRef.current?.close();
      socketRef.current = connectProgressSocket(response.task_id, {
        onMessage: (next) => {
          setProgress(next);
          if (terminalStatuses.has(next.status)) {
            setLoading(false);
            socketRef.current?.close();
            socketRef.current = null;
            loadHistory().catch(() => undefined);
          }
        },
        onError: () => {
          poll(response.task_id).catch(() => setLoading(false)).finally(() => loadHistory().catch(() => undefined));
        }
      });
    } catch (error) {
      setLoading(false);
      message.error(getApiErrorMessage(error, '生成启动失败，请检查输入文件、模板和模型配置档案。'));
    }
  };

  const download = async () => {
    const taskId = (progress as ProgressResponse | null)?.task_id;
    if (!taskId) return;
    try {
      const blob = await apiClient.downloadFile(taskId);
      downloadBlob(blob, target === 'pptx' ? 'generated.pptx' : 'generated.docx');
    } catch (error) {
      message.error(getApiErrorMessage(error, '下载失败，请确认结果文件仍在本地输出目录。'));
    }
  };

  const downloadTask = async (task: GenerateTask) => {
    try {
      const blob = await apiClient.downloadFile(task.task_id);
      const taskTarget = task.metadata?.target === 'docx' ? 'docx' : 'pptx';
      downloadBlob(blob, `generated-${task.task_id.slice(0, 8)}.${taskTarget}`);
    } catch (error) {
      message.error(getApiErrorMessage(error, '历史结果下载失败，请复用参数重新生成。'));
    }
  };

  const reuseTask = (task: GenerateTask) => {
    applyTaskParameters(task);
    message.info('已复用参数，请重新选择输入文件后生成');
  };

  const deleteTask = async (task: GenerateTask) => {
    try {
      await apiClient.deleteGenerationHistory(task.task_id);
      await loadHistory();
    } catch (error) {
      message.error(getApiErrorMessage(error, '删除记录失败，请刷新历史后重试。'));
    }
  };

  return (
    <Space orientation="vertical" size={18} className="generator-shell wide">
      <div className="generator-heading">
        <Typography.Title className="generator-title">智能生成</Typography.Title>
        <Typography.Paragraph className="generator-subtitle">
          文件、风格、模型和历史在同一处完成。
        </Typography.Paragraph>
        <Space wrap>
          <Tag color={systemHealth?.llm_provider === 'stub' ? 'green' : 'gold'}>LLM {systemHealth?.llm_provider || 'stub'}</Tag>
          <Tag color={systemHealth?.ppt_renderer === 'stub' ? 'green' : 'gold'}>PPT {systemHealth?.ppt_renderer || 'stub'}</Tag>
          <Tag color={systemHealth?.ppt_compliance_gate === 'error' ? 'red' : 'blue'}>合规 {systemHealth?.ppt_compliance_gate || 'warn'}</Tag>
        </Space>
      </div>
      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} xl={11}>
          <Space orientation="vertical" size={16} className="wide">
            <Card size="small" title="输入文件" className="tool-card"><FileUpload file={file} onChange={setFile} /></Card>
            <Card size="small" title="生成进度" className="tool-card"><ProgressBar progress={progress} /></Card>
            <Card size="small" title="结果下载" className="tool-card"><ResultPreview progress={progress} onDownload={download} /></Card>
          </Space>
        </Col>
        <Col xs={24} xl={6}>
          <Card size="small" title="生成参数" className="parameter-card">
          <Typography.Paragraph type="secondary" className="compact-help">
            默认使用外网 stub 本地流程；选择 NGA 档案后需内网适配器接入。
          </Typography.Paragraph>
          <GenerateForm
            target={target}
            slides={slides}
            templateId={templateId}
            colorSchemeId={colorSchemeId}
            userId={userId}
            templates={templates}
            colorSchemes={colors}
            users={users}
            loading={loading}
            onChange={(values) => {
              if (values.target) setTarget(values.target);
              if (values.slides !== undefined) setSlides(values.slides);
              if ('templateId' in values) setTemplateId(values.templateId);
              if ('colorSchemeId' in values) setColorSchemeId(values.colorSchemeId);
              if ('userId' in values) setUserId(values.userId);
            }}
            onSubmit={start}
          />
          </Card>
        </Col>
        <Col xs={24} xl={7}>
          <Card size="small" title="个人生成历史" className="tool-card">
          <GenerationHistory
            compact
            showTitle={false}
            tasks={history}
            loading={historyLoading}
            onRefresh={loadHistory}
            onDownload={downloadTask}
            onReuse={reuseTask}
            onDelete={deleteTask}
          />
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
