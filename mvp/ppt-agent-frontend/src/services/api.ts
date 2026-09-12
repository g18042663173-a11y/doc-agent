import axios from 'axios';
import type {
  ChartRecommendation,
  AICodingPromptResponse,
  AICodingRenderRequest,
  AICodingRenderResponse,
  ColorScheme,
  GenerateRequest,
  GenerateResponse,
  GenerateTask,
  ProgressResponse,
  SystemHealth,
  TemplateConfig,
  UserConfig
} from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';

export function getApiErrorMessage(error: unknown, fallback = '操作失败，请检查当前配置后重试。') {
  const response = (error as { response?: { status?: number; data?: unknown } } | null)?.response;
  const data = response?.data;
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail) && detail.length > 0) return '请求参数不完整，请检查表单后重试。';
  }
  const message = error instanceof Error ? error.message : '';
  if (/NGAClient|internal-network adapter/i.test(message)) return 'NGA 真实适配器尚未接入；外网阶段请使用 stub 默认流程。';
  if (/HuaweiSkillRenderer|hw_skill/i.test(message)) return '华为渲染 Skill 尚未接入；外网阶段请使用 stub 渲染器。';
  if (/network/i.test(message)) return '无法连接本地服务，请确认后端已启动。';
  if (response?.status === 404) return '资源不存在或文件已被移动，请刷新后重试。';
  if (response?.status === 400) return '请求内容无法处理，请检查文件格式和参数。';
  if (message && !/^Request failed with status code/i.test(message)) return message;
  return fallback;
}

class APIClient {
  private client = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000
  });

  async startGeneration(file: File, request: GenerateRequest): Promise<GenerateResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('target', request.target);
    formData.append('slides', String(request.slides));
    if (request.template_id) formData.append('template_id', request.template_id);
    if (request.color_scheme_id) formData.append('color_scheme_id', request.color_scheme_id);
    if (request.user_id) formData.append('user_id', request.user_id);
    if (request.profile_id) formData.append('profile_id', request.profile_id);
    const response = await this.client.post('/generate/start', formData);
    return response.data;
  }

  async getProgress(taskId: string): Promise<ProgressResponse> {
    const response = await this.client.get(`/generate/progress/${taskId}`);
    return response.data;
  }

  async downloadFile(taskId: string): Promise<Blob> {
    const response = await this.client.get(`/generate/download/${taskId}`, { responseType: 'blob' });
    return response.data;
  }

  async getGenerationHistory(limit = 50): Promise<{ tasks: GenerateTask[] }> {
    const response = await this.client.get('/generate/history', { params: { limit } });
    return response.data;
  }

  async getGenerationHistoryItem(taskId: string): Promise<GenerateTask> {
    const response = await this.client.get(`/generate/history/${taskId}`);
    return response.data;
  }

  async deleteGenerationHistory(taskId: string, deleteFiles = false): Promise<{ success: boolean }> {
    const response = await this.client.delete(`/generate/history/${taskId}`, { params: { delete_files: deleteFiles } });
    return response.data;
  }

  async buildAICodingPrompt(file: File, target: 'docx' | 'pptx', slides: number): Promise<AICodingPromptResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('target', target);
    formData.append('slides', String(slides));
    const response = await this.client.post('/aicoding/prompt', formData);
    return response.data;
  }

  async renderAICodingOutput(payload: AICodingRenderRequest): Promise<AICodingRenderResponse> {
    const response = await this.client.post('/aicoding/render', payload);
    return response.data;
  }

  async createUser(userData: Partial<UserConfig>): Promise<{ success: boolean; user_id: string; user: UserConfig }> {
    const response = await this.client.post('/users/create', userData);
    return response.data;
  }

  async getUsers(): Promise<{ users: UserConfig[] }> {
    const response = await this.client.get('/users/list');
    return response.data;
  }

  async getUser(userId: string): Promise<UserConfig> {
    const response = await this.client.get(`/users/${userId}`);
    return response.data;
  }

  async updateUser(userId: string, updates: Partial<UserConfig>): Promise<UserConfig> {
    const response = await this.client.put(`/users/${userId}`, updates);
    return response.data;
  }

  async deleteUser(userId: string): Promise<{ success: boolean }> {
    const response = await this.client.delete(`/users/${userId}`);
    return response.data;
  }

  async switchUser(userId: string): Promise<UserConfig> {
    const response = await this.client.post(`/users/switch/${userId}`);
    return response.data;
  }

  async testConnection(ngaEndpoint: string, authToken: string): Promise<{ success: boolean; message: string }> {
    const response = await this.client.post('/users/test-connection', {
      nga_endpoint: ngaEndpoint,
      auth_token: authToken
    });
    return response.data;
  }

  async getTemplates(category?: string): Promise<{ templates: TemplateConfig[] }> {
    const response = await this.client.get('/templates/list', { params: category ? { category } : {} });
    return response.data;
  }

  async importTemplate(file: File, name: string, category: string): Promise<{ success: boolean; template_id: string; style_summary?: TemplateConfig['style_summary'] }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', name);
    formData.append('category', category);
    const response = await this.client.post('/templates/import', formData);
    return response.data;
  }

  async getColorSchemes(category?: string): Promise<{ schemes: ColorScheme[] }> {
    const response = await this.client.get('/colors/list', { params: category ? { category } : {} });
    return response.data;
  }

  async recommendColors(scenario: string): Promise<{ recommendations: Array<{ scheme_id: string; confidence: number; reason: string }> }> {
    const response = await this.client.get('/colors/recommend', { params: { scenario } });
    return response.data;
  }

  async createColorScheme(schemeData: Partial<ColorScheme>): Promise<{ success: boolean; scheme_id: string }> {
    const response = await this.client.post('/colors/create', schemeData);
    return response.data;
  }

  async recommendChart(data_description: string, data_characteristics: Record<string, unknown>): Promise<{ recommendation: ChartRecommendation }> {
    const response = await this.client.post('/charts/recommend', { data_description, data_characteristics });
    return response.data;
  }

  async generateChart(payload: Record<string, unknown>): Promise<{ chart: Record<string, unknown> }> {
    const response = await this.client.post('/charts/generate', payload);
    return response.data;
  }

  async getSmartArtTypes(): Promise<{ types: string[] }> {
    const response = await this.client.get('/smartart/types');
    return response.data;
  }

  async generateSmartArt(payload: Record<string, unknown>): Promise<{ smartart: Record<string, unknown> }> {
    const response = await this.client.post('/smartart/generate', payload);
    return response.data;
  }

  async exportConfig(): Promise<Record<string, unknown>> {
    const response = await this.client.get('/config/export');
    return response.data;
  }

  async importConfig(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    const response = await this.client.post('/config/import', payload);
    return response.data;
  }

  async getSystemHealth(): Promise<SystemHealth> {
    const response = await this.client.get('/system/health');
    return response.data;
  }
}

export const apiClient = new APIClient();
