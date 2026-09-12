import { Progress, Space, Tag } from 'antd';
import type { ProgressResponse } from '@/types';

export default function ProgressBar({ progress }: { progress: ProgressResponse | null }) {
  if (!progress) return null;
  const status = progress.status === 'failed' ? 'exception' : progress.status === 'completed' ? 'success' : 'active';
  return (
    <Space orientation="vertical" size={8} className="wide">
      <div className="status-line">
        <Tag color={progress.status === 'completed' ? 'green' : progress.status === 'failed' ? 'red' : 'blue'}>
          {progress.status}
        </Tag>
        <span className="muted-text">{progress.current_step}</span>
      </div>
      <Progress percent={progress.progress} status={status} />
      {progress.error && <span className="error-text">{progress.error}</span>}
    </Space>
  );
}
