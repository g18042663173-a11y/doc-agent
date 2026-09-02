import { DownloadOutlined } from '@ant-design/icons';
import { Button, Card, Empty } from 'antd';
import { apiClient } from '@/services/api';
import { downloadBlob } from '@/services/fileService';
import { useDocumentStore } from '@/store';

export default function Export() {
  const progress = useDocumentStore((state) => state.progress);
  const download = async () => {
    if (!progress?.task_id) return;
    const blob = await apiClient.downloadFile(progress.task_id);
    downloadBlob(blob, 'generated');
  };

  if (progress?.status !== 'completed') return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  return (
    <Card size="small">
      <Button type="primary" icon={<DownloadOutlined />} onClick={download}>下载</Button>
    </Card>
  );
}
