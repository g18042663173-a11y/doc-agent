import { DownloadOutlined } from '@ant-design/icons';
import { Alert, Button, Space, Tag, Typography } from 'antd';
import type { ProgressResponse } from '@/types';

export default function ResultPreview({ progress, onDownload }: { progress: ProgressResponse | null; onDownload: () => void }) {
  if (progress?.status === 'failed') {
    return <Alert type="error" showIcon title={progress.friendly_error || '生成失败'} description={progress.error} />;
  }
  if (progress?.status !== 'completed') {
    return <Typography.Text type="secondary">生成完成后会在这里显示下载入口。</Typography.Text>;
  }
  const report = progress.compliance_report;
  const errorCount = report?.items.filter((item) => item.severity === 'Error').length || 0;
  const warningCount = report?.items.filter((item) => item.severity === 'Warning').length || 0;
  return (
    <Space orientation="vertical" size={12} className="wide">
      <div className="result-ready">
        <div className="result-file">
          <Typography.Text strong>generated</Typography.Text>
          <Typography.Text type="secondary">可编辑 Office 文件</Typography.Text>
        </div>
        <Button type="primary" icon={<DownloadOutlined />} onClick={onDownload}>
          下载
        </Button>
      </div>
      {report && (
        <Alert
          type={errorCount ? 'warning' : 'success'}
          showIcon
          title={
            <Space wrap>
              <span>合规检查 {report.score}</span>
              <Tag color={errorCount ? 'red' : 'green'}>{errorCount} Error</Tag>
              <Tag color={warningCount ? 'gold' : 'green'}>{warningCount} Warning</Tag>
            </Space>
          }
          description={report.summary}
        />
      )}
    </Space>
  );
}
