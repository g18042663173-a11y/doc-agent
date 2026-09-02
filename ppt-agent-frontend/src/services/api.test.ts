import { beforeEach, describe, expect, it, vi } from 'vitest';

const http = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn()
}));

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => http)
  }
}));

import { apiClient, getApiErrorMessage } from './api';

describe('apiClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('starts generation with multipart data', async () => {
    http.post.mockResolvedValueOnce({ data: { task_id: 'task', status: 'processing', message: 'started' } });

    const file = new File(['# Demo'], 'input.md', { type: 'text/markdown' });
    const result = await apiClient.startGeneration(file, {
      target: 'pptx',
      slides: 8,
      template_id: 'tpl',
      color_scheme_id: 'scheme',
      user_id: 'user'
    });

    expect(result.task_id).toBe('task');
    expect(http.post).toHaveBeenCalledWith('/generate/start', expect.any(FormData));
    const form = http.post.mock.calls[0][1] as FormData;
    expect(form.get('file')).toBe(file);
    expect(form.get('target')).toBe('pptx');
    expect(form.get('slides')).toBe('8');
    expect(form.get('template_id')).toBe('tpl');
    expect(form.get('color_scheme_id')).toBe('scheme');
    expect(form.get('user_id')).toBe('user');
  });

  it('calls generation progress and download endpoints', async () => {
    const blob = new Blob(['pptx']);
    http.get.mockResolvedValueOnce({ data: { task_id: 'task', status: 'completed' } });
    await expect(apiClient.getProgress('task')).resolves.toMatchObject({ status: 'completed' });
    expect(http.get).toHaveBeenCalledWith('/generate/progress/task');

    http.get.mockResolvedValueOnce({ data: blob });
    await expect(apiClient.downloadFile('task')).resolves.toBe(blob);
    expect(http.get).toHaveBeenCalledWith('/generate/download/task', { responseType: 'blob' });
  });

  it('calls generation history endpoints', async () => {
    http.get.mockResolvedValueOnce({ data: { tasks: [] } });
    await expect(apiClient.getGenerationHistory(12)).resolves.toEqual({ tasks: [] });
    expect(http.get).toHaveBeenCalledWith('/generate/history', { params: { limit: 12 } });

    http.get.mockResolvedValueOnce({ data: { task_id: 'task' } });
    await expect(apiClient.getGenerationHistoryItem('task')).resolves.toMatchObject({ task_id: 'task' });
    expect(http.get).toHaveBeenCalledWith('/generate/history/task');

    http.delete.mockResolvedValueOnce({ data: { success: true } });
    await expect(apiClient.deleteGenerationHistory('task', true)).resolves.toEqual({ success: true });
    expect(http.delete).toHaveBeenCalledWith('/generate/history/task', { params: { delete_files: true } });
  });

  it('calls AICoding bridge endpoints', async () => {
    const file = new File(['# Demo'], 'input.md', { type: 'text/markdown' });
    http.post.mockResolvedValueOnce({ data: { prompt: 'copy me', target: 'docx', slides: 8, document_ir: {}, source_summary: 'md' } });
    await expect(apiClient.buildAICodingPrompt(file, 'docx', 8)).resolves.toMatchObject({ prompt: 'copy me' });
    expect(http.post).toHaveBeenCalledWith('/aicoding/prompt', expect.any(FormData));
    const form = http.post.mock.calls[0][1] as FormData;
    expect(form.get('file')).toBe(file);
    expect(form.get('target')).toBe('docx');
    expect(form.get('slides')).toBe('8');

    http.post.mockResolvedValueOnce({ data: { task_id: 'task', status: 'completed', result: 'out.docx', warnings: [] } });
    await expect(apiClient.renderAICodingOutput({ target: 'docx', model_output: '{}' })).resolves.toMatchObject({ task_id: 'task' });
    expect(http.post).toHaveBeenCalledWith('/aicoding/render', { target: 'docx', model_output: '{}' });
  });

  it('calls user and config endpoints', async () => {
    http.post.mockResolvedValue({ data: { success: true, user_id: 'user', user: { user_id: 'user' } } });
    http.get.mockResolvedValue({ data: { users: [] } });
    http.put.mockResolvedValue({ data: { user_id: 'user', user_name: 'Renamed' } });
    http.delete.mockResolvedValue({ data: { success: true } });

    await apiClient.createUser({ user_name: 'User' });
    await apiClient.getUsers();
    await apiClient.getUser('user');
    await apiClient.updateUser('user', { user_name: 'Renamed' });
    await apiClient.deleteUser('user');
    await apiClient.switchUser('user');
    await apiClient.testConnection('http://example.test/v1', 'token');
    await apiClient.exportConfig();
    await apiClient.importConfig({ users: [] });
    await apiClient.getSystemHealth();

    expect(http.post).toHaveBeenCalledWith('/users/create', { user_name: 'User' });
    expect(http.get).toHaveBeenCalledWith('/users/list');
    expect(http.get).toHaveBeenCalledWith('/users/user');
    expect(http.put).toHaveBeenCalledWith('/users/user', { user_name: 'Renamed' });
    expect(http.delete).toHaveBeenCalledWith('/users/user');
    expect(http.post).toHaveBeenCalledWith('/users/switch/user');
    expect(http.post).toHaveBeenCalledWith('/users/test-connection', { nga_endpoint: 'http://example.test/v1', auth_token: 'token' });
    expect(http.get).toHaveBeenCalledWith('/config/export');
    expect(http.post).toHaveBeenCalledWith('/config/import', { users: [] });
    expect(http.get).toHaveBeenCalledWith('/system/health');
  });

  it('calls design endpoints with expected params and payloads', async () => {
    http.get.mockResolvedValue({ data: {} });
    http.post.mockResolvedValue({ data: {} });

    await apiClient.getTemplates('business');
    await apiClient.importTemplate(new File(['pptx'], 'template.pptx'), 'Template', 'business');
    await apiClient.getColorSchemes('tech');
    await apiClient.recommendColors('商务报告');
    await apiClient.createColorScheme({ name: 'Scheme' });
    await apiClient.recommendChart('trend', { data_type: 'time_series' });
    await apiClient.generateChart({ chart_type: 'line' });
    await apiClient.getSmartArtTypes();
    await apiClient.generateSmartArt({ nodes: [] });

    expect(http.get).toHaveBeenCalledWith('/templates/list', { params: { category: 'business' } });
    expect(http.post).toHaveBeenCalledWith('/templates/import', expect.any(FormData));
    expect(http.get).toHaveBeenCalledWith('/colors/list', { params: { category: 'tech' } });
    expect(http.get).toHaveBeenCalledWith('/colors/recommend', { params: { scenario: '商务报告' } });
    expect(http.post).toHaveBeenCalledWith('/colors/create', { name: 'Scheme' });
    expect(http.post).toHaveBeenCalledWith('/charts/recommend', { data_description: 'trend', data_characteristics: { data_type: 'time_series' } });
    expect(http.post).toHaveBeenCalledWith('/charts/generate', { chart_type: 'line' });
    expect(http.get).toHaveBeenCalledWith('/smartart/types');
    expect(http.post).toHaveBeenCalledWith('/smartart/generate', { nodes: [] });
  });

  it('extracts actionable api error messages', () => {
    expect(getApiErrorMessage({ response: { status: 400, data: { detail: '仅支持 .pptx 文件' } } })).toBe('仅支持 .pptx 文件');
    expect(getApiErrorMessage(new Error('Network Error'))).toBe('无法连接本地服务，请确认后端已启动。');
    expect(getApiErrorMessage({ response: { status: 404, data: {} } }, 'fallback')).toBe('资源不存在或文件已被移动，请刷新后重试。');
  });
});
