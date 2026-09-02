import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Divider,
  Input,
  InputNumber,
  Row,
  Segmented,
  Space,
  Tag,
  Typography
} from 'antd';
import { CopyOutlined, FileSearchOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { useState } from 'react';
import FileUpload from '@/components/DocumentGenerator/FileUpload';
import ResultPreview from '@/components/DocumentGenerator/ResultPreview';
import { apiClient, getApiErrorMessage } from '@/services/api';
import { downloadBlob } from '@/services/fileService';
import type { AICodingPromptResponse, AICodingRenderResponse, ProgressResponse, TargetType } from '@/types';

const { TextArea } = Input;

export default function AICodingBridge() {
  const { message } = App.useApp();
  const [file, setFile] = useState<File | null>(null);
  const [target, setTarget] = useState<TargetType>('docx');
  const [slides, setSlides] = useState(8);
  const [promptData, setPromptData] = useState<AICodingPromptResponse | null>(null);
  const [modelOutput, setModelOutput] = useState('');
  const [renderResult, setRenderResult] = useState<AICodingRenderResponse | null>(null);
  const [promptLoading, setPromptLoading] = useState(false);
  const [renderLoading, setRenderLoading] = useState(false);
  const busy = promptLoading || renderLoading;

  const clearGeneratedState = () => {
    setPromptData(null);
    setModelOutput('');
    setRenderResult(null);
  };

  const handleFileChange = (nextFile: File | null) => {
    setFile(nextFile);
    clearGeneratedState();
  };

  const handleTargetChange = (nextTarget: TargetType) => {
    setTarget(nextTarget);
    clearGeneratedState();
  };

  const handleSlidesChange = (value: number | null) => {
    setSlides(Number(value || 8));
    if (target === 'pptx') {
      clearGeneratedState();
    }
  };

  const generatePrompt = async () => {
    if (!file) {
      message.error('请选择输入文件');
      return;
    }
    setPromptLoading(true);
    setModelOutput('');
    setRenderResult(null);
    try {
      const response = await apiClient.buildAICodingPrompt(file, target, slides);
      setPromptData(response);
      message.success('AICoding prompt 已生成');
    } catch (error) {
      message.error(getApiErrorMessage(error, 'Prompt 生成失败，请检查输入文件。'));
    } finally {
      setPromptLoading(false);
    }
  };

  const copyPrompt = async () => {
    if (!promptData?.prompt) return;
    await navigator.clipboard.writeText(promptData.prompt);
    message.success('已复制 prompt');
  };

  const renderOutput = async () => {
    if (!modelOutput.trim()) {
      message.error('请粘贴 AICoding 输出 JSON');
      return;
    }
    setRenderLoading(true);
    try {
      const response = await apiClient.renderAICodingOutput({
        target,
        model_output: modelOutput,
        original_filename: file?.name,
        slides: target === 'pptx' ? slides : undefined
      });
      setRenderResult(response);
      message.success('文件已生成');
    } catch (error) {
      message.error(getApiErrorMessage(error, 'AICoding JSON 处理失败，请检查字段是否符合 IR 规范。'));
    } finally {
      setRenderLoading(false);
    }
  };

  const downloadResult = async () => {
    if (!renderResult?.task_id) return;
    try {
      const blob = await apiClient.downloadFile(renderResult.task_id);
      downloadBlob(blob, target === 'pptx' ? 'aicoding-generated.pptx' : 'aicoding-generated.docx');
    } catch (error) {
      message.error(getApiErrorMessage(error, '下载失败，请确认结果文件仍在本地。'));
    }
  };

  const progress: ProgressResponse | null = renderResult
    ? {
      task_id: renderResult.task_id,
      status: renderResult.status,
      progress: 100,
      current_step: 'AICoding 手动桥接完成',
      compliance_report: renderResult.compliance_report || null,
      result: renderResult.result
    }
    : null;

  return (
    <Space orientation="vertical" size={18} className="generator-shell wide">
      <div className="generator-heading">
        <Typography.Title className="generator-title">AICoding 桥接</Typography.Title>
        <Typography.Paragraph className="generator-subtitle">
          Office 输入先转结构化 prompt，再粘贴 AICoding JSON 生成文件。
        </Typography.Paragraph>
        <Space wrap>
          <Tag color="blue">manual</Tag>
          <Tag color={target === 'docx' ? 'purple' : 'volcano'}>{target.toUpperCase()}</Tag>
          <Tag color="green">本地渲染</Tag>
        </Space>
      </div>

      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} lg={9}>
          <Space orientation="vertical" size={16} className="wide">
            <Card size="small" title="输入文件" className="tool-card">
              <FileUpload file={file} onChange={handleFileChange} disabled={busy} />
              <Divider />
              <Space orientation="vertical" size={12} className="wide">
                <Segmented
                  block
                  disabled={busy}
                  value={target}
                  options={[
                    { label: 'Word', value: 'docx' },
                    { label: 'PPTX', value: 'pptx' }
                  ]}
                  onChange={(value) => handleTargetChange(value as TargetType)}
                />
                <Space orientation="vertical" size={6} className="wide">
                  <Typography.Text type="secondary">PPT 页数</Typography.Text>
                  <InputNumber
                    className="wide"
                    min={1}
                    max={30}
                    value={slides}
                    disabled={target !== 'pptx' || busy}
                    onChange={handleSlidesChange}
                  />
                </Space>
                <Button
                  type="primary"
                  icon={<FileSearchOutlined />}
                  loading={promptLoading}
                  disabled={renderLoading}
                  onClick={generatePrompt}
                  data-testid="aicoding-prompt"
                >
                  生成 prompt
                </Button>
              </Space>
            </Card>

            <Card size="small" title="结果下载" className="tool-card">
              <ResultPreview progress={progress} onDownload={downloadResult} />
              {renderResult?.compliance_report && (
                <Alert
                  className="compact-alert"
                  type={renderResult.compliance_report.score >= 80 ? 'success' : 'warning'}
                  showIcon
                  title={`格式检查 ${renderResult.compliance_report.score}`}
                  description={renderResult.compliance_report.summary}
                />
              )}
            </Card>
          </Space>
        </Col>

        <Col xs={24} lg={8}>
          <Card
            size="small"
            title="AICoding prompt"
            className="tool-card"
            extra={<Button size="small" icon={<CopyOutlined />} disabled={!promptData?.prompt} onClick={copyPrompt}>复制</Button>}
          >
            {promptData?.source_summary && <Alert className="compact-alert" type="info" showIcon title={promptData.source_summary} />}
            <TextArea
              value={promptData?.prompt || ''}
              readOnly
              rows={22}
              placeholder="生成后复制到 AICoding 终端"
              data-testid="aicoding-prompt-text"
            />
          </Card>
        </Col>

        <Col xs={24} lg={7}>
          <Card size="small" title="AICoding JSON" className="tool-card">
            <Space orientation="vertical" size={12} className="wide">
              <TextArea
                value={modelOutput}
                rows={22}
                placeholder="粘贴 AICoding 输出 JSON"
                onChange={(event) => setModelOutput(event.target.value)}
                data-testid="aicoding-json"
              />
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={renderLoading}
                disabled={promptLoading}
                onClick={renderOutput}
                data-testid="aicoding-render"
              >
                校验并生成
              </Button>
            </Space>
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
