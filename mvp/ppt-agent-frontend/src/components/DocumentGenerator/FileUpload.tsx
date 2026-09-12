import { InboxOutlined } from '@ant-design/icons';
import { Upload } from 'antd';

interface FileUploadProps {
  file: File | null;
  onChange: (file: File | null) => void;
  disabled?: boolean;
}

export default function FileUpload({ file, onChange, disabled = false }: FileUploadProps) {
  return (
    <div className="upload-surface">
      <Upload.Dragger
        accept=".md,.docx,.pptx,.xlsx,.xlsm"
        disabled={disabled}
        maxCount={1}
        beforeUpload={(nextFile) => {
          onChange(nextFile);
          return false;
        }}
        onRemove={() => onChange(null)}
        fileList={file ? [{ uid: 'local', name: file.name, status: 'done' as const }] : []}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">上传 md / docx / pptx / xlsx / xlsm</p>
      </Upload.Dragger>
    </div>
  );
}
