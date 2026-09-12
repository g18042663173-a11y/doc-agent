import { Card, Empty, Progress, Space, Tag } from 'antd';
import { useDocumentStore } from '@/store';

export default function Preview() {
  const progress = useDocumentStore((state) => state.progress);
  if (!progress) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  return (
    <Card size="small">
      <Space orientation="vertical" className="wide">
        <Tag>{progress.status}</Tag>
        <Progress percent={progress.progress} />
        <pre className="json-panel">{JSON.stringify(progress, null, 2)}</pre>
      </Space>
    </Card>
  );
}
