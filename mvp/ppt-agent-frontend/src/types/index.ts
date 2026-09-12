export type TargetType = 'pptx' | 'docx';

export interface UserConfig {
  user_id: string;
  user_name: string;
  nga_endpoint: string;
  auth_token: string;
  llm_provider: string;
  llm_model: string;
  ppt_renderer: string;
  default_template?: string | null;
  default_color_scheme?: string | null;
  last_used?: string;
}

export interface TemplateConfig {
  template_id: string;
  name: string;
  category: string;
  description: string;
  thumbnail?: string | null;
  preview?: string | null;
  is_system: boolean;
  style_summary?: TemplateStyleSummary | null;
}

export interface TemplateStyleSummary {
  mode?: string;
  note?: string;
  slide_size?: {
    width_inches?: number;
    height_inches?: number;
    ratio?: string;
  };
  master_count?: number;
  slide_count?: number;
  font_config?: Record<string, string>;
  colors?: Record<string, string>;
}

export interface ColorScheme {
  scheme_id: string;
  name: string;
  category: string;
  description?: string | null;
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  background_color: string;
  text_color: string;
  is_system: boolean;
}

export interface GenerateRequest {
  target: TargetType;
  slides: number;
  template_id?: string;
  color_scheme_id?: string;
  user_id?: string;
  profile_id?: string;
}

export interface GenerateResponse {
  task_id: string;
  status: string;
  message: string;
}

export interface ProgressResponse {
  task_id: string;
  status: string;
  progress: number;
  current_step: string;
  result?: string | null;
  error?: string | null;
  error_type?: string | null;
  friendly_error?: string | null;
  compliance_report?: ComplianceReport | null;
  metadata?: GenerateTaskMetadata | null;
}

export interface ComplianceReport {
  score: number;
  summary: string;
  items: ComplianceItem[];
}

export interface ComplianceItem {
  severity: 'Error' | 'Warning' | 'Info';
  code: string;
  message: string;
  slide_index?: number | null;
}

export interface GenerateTaskMetadata {
  original_filename?: string | null;
  source_type?: string | null;
  target?: TargetType | string | null;
  slides?: number | null;
  template_id?: string | null;
  color_scheme_id?: string | null;
  user_id?: string | null;
  profile_id?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface GenerateTask extends ProgressResponse {
  metadata: GenerateTaskMetadata;
}

export interface AICodingPromptResponse {
  prompt: string;
  target: TargetType;
  slides: number;
  document_ir: Record<string, unknown>;
  source_summary: string;
}

export interface AICodingRenderRequest {
  target: TargetType;
  model_output: string | Record<string, unknown>;
  template_id?: string;
  color_scheme_id?: string;
  original_filename?: string;
  slides?: number;
}

export interface AICodingRenderResponse {
  task_id: string;
  status: string;
  result: string;
  compliance_report?: ComplianceReport | null;
  warnings: string[];
}

export interface ChartRecommendation {
  chart_type: string;
  confidence: number;
  reason: string;
  data_requirements: string[];
  styling_tips: string[];
}

export interface SystemHealth {
  status: string;
  version: string;
  data_dir: string;
  output_dir: string;
  llm_provider: string;
  ppt_renderer: string;
  ppt_compliance_gate?: string;
  preview_export_available?: boolean;
}
