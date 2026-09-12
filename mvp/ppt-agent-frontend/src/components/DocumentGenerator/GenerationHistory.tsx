import { DeleteOutlined, DownloadOutlined, ReloadOutlined, RetweetOutlined } from '@ant-design/icons';
import { Button, Empty, Space, Table, Tag, Tooltip, Typography } from 'antd';
import type { GenerateTask } from '@/types';

interface GenerationHistoryProps {
  tasks: GenerateTask[];
  loading?: boolean;
  compact?: boolean;
  showTitle?: boolean;
  onRefresh?: () => void;
  onDownload?: (task: GenerateTask) => void;
  onReuse?: (task: GenerateTask) => void;
  onDelete?: (task: GenerateTask) => void;
}

const statusColors: Record<string, string> = {
  completed: 'green',
  failed: 'red',
  processing: 'blue',
  queued: 'gold',
  not_found: 'default'
};

export default function GenerationHistory({ tasks, loading, compact, showTitle = true, onRefresh, onDownload, onReuse, onDelete }: GenerationHistoryProps) {
  if (!loading && tasks.length === 0) {
    return (
      <Space orientation="vertical" size={12} className="wide">
        <div className="panel-toolbar">
          {showTitle ? <Typography.Text strong>最近生成</Typography.Text> : <span />}
          {onRefresh && <Button size="small" icon={<ReloadOutlined />} onClick={onRefresh}>刷新</Button>}
        </div>
        <Empty description="还没有生成记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Space>
    );
  }

  return (
    <Space orientation="vertical" size={12} className="wide">
      <div className="panel-toolbar">
        {showTitle ? <Typography.Text strong>最近生成</Typography.Text> : <span />}
        {onRefresh && <Button size="small" icon={<ReloadOutlined />} onClick={onRefresh}>刷新</Button>}
      </div>
      <Table
        size="small"
        rowKey="task_id"
        loading={loading}
        dataSource={tasks}
        pagination={compact ? false : { pageSize: 6 }}
        columns={[
          {
            title: '文件',
            render: (_, record) => (
              <Space orientation="vertical" size={0}>
                <Typography.Text>{record.metadata?.original_filename || '未命名输入'}</Typography.Text>
                <Typography.Text type="secondary">{record.metadata?.target?.toUpperCase() || '-'}</Typography.Text>
              </Space>
            )
          },
          {
            title: '状态',
            render: (_, record) => (
              <Space orientation="vertical" size={2}>
                <Tag color={statusColors[record.status] || 'default'}>{record.status}</Tag>
                {record.compliance_report && <Tag color={record.compliance_report.score >= 80 ? 'green' : 'gold'}>合规 {record.compliance_report.score}</Tag>}
              </Space>
            )
          },
          ...(!compact ? [{
            title: '参数',
            render: (_: unknown, record: GenerateTask) => (
              <Typography.Text type="secondary">
                {record.metadata?.slides || '-'} 页 · {record.metadata?.template_id || '默认模板'} · {record.metadata?.color_scheme_id || '默认配色'}
              </Typography.Text>
            )
          }] : []),
          {
            title: '时间',
            render: (_, record) => {
              const value = record.metadata?.updated_at || record.metadata?.created_at;
              return value ? new Date(value).toLocaleString() : '-';
            }
          },
          {
            title: '操作',
            render: (_, record) => (
              <Space>
                {onDownload && (
                  <Tooltip title={record.status === 'completed' ? '下载结果' : '仅完成任务可下载'}>
                    <Button size="small" aria-label={`下载 ${record.task_id}`} icon={<DownloadOutlined />} disabled={record.status !== 'completed'} onClick={() => onDownload(record)} />
                  </Tooltip>
                )}
                {onReuse && (
                  <Tooltip title="复用参数">
                    <Button size="small" aria-label={`复用 ${record.task_id}`} icon={<RetweetOutlined />} onClick={() => onReuse(record)} />
                  </Tooltip>
                )}
                {onDelete && (
                  <Tooltip title="删除记录">
                    <Button size="small" danger aria-label={`删除 ${record.task_id}`} icon={<DeleteOutlined />} onClick={() => onDelete(record)} />
                  </Tooltip>
                )}
              </Space>
            )
          }
        ]}
      />
    </Space>
  );
}
