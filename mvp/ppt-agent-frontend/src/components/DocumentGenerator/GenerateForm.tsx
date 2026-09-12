import { FilePptOutlined } from '@ant-design/icons';
import { Button, Form, Select, Slider } from 'antd';
import type { ColorScheme, TargetType, TemplateConfig, UserConfig } from '@/types';

interface GenerateFormProps {
  target: TargetType;
  slides: number;
  templateId?: string;
  colorSchemeId?: string;
  userId?: string;
  templates: TemplateConfig[];
  colorSchemes: ColorScheme[];
  users: UserConfig[];
  loading: boolean;
  onChange: (values: Partial<{ target: TargetType; slides: number; templateId?: string; colorSchemeId?: string; userId?: string }>) => void;
  onSubmit: () => void;
}

export default function GenerateForm(props: GenerateFormProps) {
  return (
    <Form layout="vertical" className="control-form">
      <Form.Item label="输出">
        <Select
          value={props.target}
          options={[
            { value: 'pptx', label: 'PPTX' },
            { value: 'docx', label: 'DOCX' }
          ]}
          onChange={(target) => props.onChange({ target })}
        />
      </Form.Item>
      <Form.Item label="页数">
        <Slider min={5} max={12} value={props.slides} onChange={(slides) => props.onChange({ slides })} />
      </Form.Item>
      <Form.Item label="模板">
        <Select
          allowClear
          value={props.templateId}
          options={props.templates.map((template) => ({ value: template.template_id, label: template.name }))}
          onChange={(templateId) => props.onChange({ templateId })}
        />
      </Form.Item>
      <Form.Item label="颜色">
        <Select
          allowClear
          value={props.colorSchemeId}
          options={props.colorSchemes.map((scheme) => ({ value: scheme.scheme_id, label: scheme.name }))}
          onChange={(colorSchemeId) => props.onChange({ colorSchemeId })}
        />
      </Form.Item>
      <Form.Item label="模型配置档案">
        <Select
          allowClear
          placeholder="默认 stub 或当前档案"
          value={props.userId}
          options={props.users.map((user) => ({ value: user.user_id, label: user.user_name }))}
          onChange={(userId) => props.onChange({ userId })}
        />
      </Form.Item>
      <Button type="primary" block icon={<FilePptOutlined />} loading={props.loading} onClick={props.onSubmit} data-testid="generate-submit">
        生成
      </Button>
    </Form>
  );
}
