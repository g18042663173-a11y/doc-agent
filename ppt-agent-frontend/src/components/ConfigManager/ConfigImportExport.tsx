import { DownloadOutlined, UploadOutlined } from '@ant-design/icons';
import { Alert, App, Button, Card, Space, Upload } from 'antd';
import { apiClient, getApiErrorMessage } from '@/services/api';
import { downloadJson, readJsonFile } from '@/services/fileService';
import type { TemplateConfig, UserConfig } from '@/types';

interface ExportedConfig {
  exported_at: string;
  users: UserConfig[];
  templates?: TemplateConfig[];
  color_schemes?: unknown[];
}

export default function ConfigImportExport({ onImported }: { onImported?: () => void }) {
  const { message } = App.useApp();

  const exportConfig = async () => {
    downloadJson(await apiClient.exportConfig(), 'ppt-agent-config.json');
  };

  const importConfig = async (file: File) => {
    const data = await readJsonFile<ExportedConfig>(file);
    const result = await apiClient.importConfig({
      users: Array.isArray(data.users) ? data.users : [],
      templates: Array.isArray(data.templates) ? data.templates : [],
      color_schemes: Array.isArray(data.color_schemes) ? data.color_schemes : []
    });
    message.success(`导入完成：${JSON.stringify(result)}`);
    onImported?.();
  };

  return (
    <Card size="small" title="个人备份与恢复">
      <Space orientation="vertical" size={12} className="wide">
        <Alert
          type="info"
          showIcon
          title="配置导出会包含模型配置档案、模板元数据和自定义配色；迁移已有 token 时请保留 data/users/.encryption_key。"
          description="自定义模板会恢复元数据；若要连同原 PPTX 文件一起迁移，请按 MIGRATION.md 备份 data/templates/custom。"
        />
        <Space wrap>
          <Button icon={<DownloadOutlined />} onClick={exportConfig} data-testid="config-export">导出个人配置</Button>
          <Upload
            accept=".json"
            maxCount={1}
            showUploadList={false}
            beforeUpload={(file) => {
              importConfig(file).catch((error) => {
                message.error(getApiErrorMessage(error, '配置恢复失败，请确认 JSON 文件来自本项目导出。'));
              });
              return false;
            }}
          >
            <Button icon={<UploadOutlined />} data-testid="config-import">恢复个人配置</Button>
          </Upload>
        </Space>
      </Space>
    </Card>
  );
}
