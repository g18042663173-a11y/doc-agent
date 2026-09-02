import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { renderWithProviders } from '@/test/render';
import { useDocumentStore } from '@/store';
import Dashboard from './Dashboard';
import DataManage from './Data/Manage';
import Export from './Export';
import Preview from './Preview';
import AICodingBridge from './Generate/AICodingBridge';
import Settings from './Config/Settings';
import NGA from './Config/NGA';
import Charts from './Design/Charts';
import Colors from './Design/Colors';
import SmartArt from './Design/SmartArt';
import Templates from './Design/Templates';

const api = vi.hoisted(() => ({
  getUsers: vi.fn(),
  getTemplates: vi.fn(),
  getColorSchemes: vi.fn(),
  getGenerationHistory: vi.fn(),
  getSystemHealth: vi.fn(),
  downloadFile: vi.fn(),
  buildAICodingPrompt: vi.fn(),
  renderAICodingOutput: vi.fn(),
  exportConfig: vi.fn(),
  getSmartArtTypes: vi.fn()
}));

const fileService = vi.hoisted(() => ({
  downloadBlob: vi.fn(),
  downloadJson: vi.fn(),
  readJsonFile: vi.fn()
}));

vi.mock('@/services/api', () => ({ apiClient: api, getApiErrorMessage: (_error: unknown, fallback?: string) => fallback || 'api error' }));
vi.mock('@/services/fileService', () => fileService);

describe('pages', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useDocumentStore.setState({ taskId: null, progress: null });
    api.getUsers.mockResolvedValue({ users: [] });
    api.getTemplates.mockResolvedValue({ templates: [{ template_id: 'tpl', name: 'Template', category: 'business', description: 'Demo', is_system: true }] });
    api.getColorSchemes.mockResolvedValue({ schemes: [] });
    api.getGenerationHistory.mockResolvedValue({ tasks: [] });
    api.getSystemHealth.mockResolvedValue({
      status: 'ok',
      version: '0.1.0',
      data_dir: 'data',
      output_dir: 'outputs',
      llm_provider: 'stub',
      ppt_renderer: 'stub',
      ppt_compliance_gate: 'warn',
      preview_export_available: false
    });
    api.getSmartArtTypes.mockResolvedValue({ types: [] });
  });

  it('renders dashboard data and offline state', async () => {
    api.downloadFile.mockResolvedValueOnce(new Blob(['docx']));
    api.getTemplates.mockResolvedValueOnce({
      templates: [
        { template_id: 'tpl', name: 'Template', category: 'business', description: 'Demo', is_system: true },
        { template_id: 'custom', name: 'Custom Template', category: 'tech', description: 'Demo', is_system: false }
      ]
    });
    api.getGenerationHistory.mockResolvedValueOnce({
      tasks: [{
        task_id: 'dashboard-task',
        status: 'completed',
        progress: 100,
        current_step: 'done',
        metadata: { original_filename: 'source.md', target: 'docx', updated_at: '2026-07-06T01:02:03Z' }
      }]
    });
    renderWithProviders(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(await screen.findByText('Template')).toBeInTheDocument();
    expect(await screen.findByText('Custom Template')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('下载 dashboard-task'));
    await waitFor(() => expect(fileService.downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'generated-dashboar.docx'));

    api.getUsers.mockRejectedValueOnce(new Error('offline'));
    renderWithProviders(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(await screen.findByText('offline')).toBeInTheDocument();
  });

  it('renders preview, data manage, and export states', async () => {
    const { rerender } = renderWithProviders(<Preview />);
    expect(document.querySelector('.ant-empty')).toBeInTheDocument();

    useDocumentStore.getState().setProgress({ task_id: 'task', status: 'completed', progress: 100, current_step: 'done' });
    rerender(<Preview />);
    expect(screen.getByText('completed')).toBeInTheDocument();

    renderWithProviders(<DataManage />);
    expect(screen.getByText('task')).toBeInTheDocument();

    api.downloadFile.mockResolvedValueOnce(new Blob(['pptx']));
    renderWithProviders(<Export />);
    fireEvent.click(screen.getByRole('button', { name: /下载/ }));
    await waitFor(() => expect(fileService.downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'generated'));
  });

  it('renders AICoding bridge page', async () => {
    api.buildAICodingPrompt.mockResolvedValueOnce({
      prompt: 'PROMPT BODY',
      target: 'docx',
      slides: 8,
      document_ir: { source_type: 'md' },
      source_summary: 'md · 1 个结构块 · Demo'
    });
    const clipboard = { writeText: vi.fn().mockResolvedValue(undefined) };
    Object.assign(navigator, { clipboard });

    const { container } = renderWithProviders(<AICodingBridge />);
    expect(screen.getByText('AICoding 桥接')).toBeInTheDocument();
    expect(screen.getByTestId('aicoding-prompt')).toBeInTheDocument();

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['# Demo'], 'input.md', { type: 'text/markdown' });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByTestId('aicoding-prompt'));
    await waitFor(() => expect(api.buildAICodingPrompt).toHaveBeenCalledWith(file, 'docx', 8));
    expect(screen.getByDisplayValue('PROMPT BODY')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /复制/ }));
    await waitFor(() => expect(clipboard.writeText).toHaveBeenCalledWith('PROMPT BODY'));
  });

  it('renders AICoding pasted JSON output and downloads result', async () => {
    api.renderAICodingOutput.mockResolvedValueOnce({
      task_id: 'aicoding-task',
      status: 'completed',
      result: 'generated.docx',
      compliance_report: { score: 96, summary: 'No Word format issues found', items: [] },
      warnings: []
    });
    api.downloadFile.mockResolvedValueOnce(new Blob(['docx']));

    renderWithProviders(<AICodingBridge />);
    fireEvent.change(screen.getByTestId('aicoding-json'), { target: { value: '{"title":"Demo","blocks":[]}' } });
    fireEvent.click(screen.getByTestId('aicoding-render'));

    await waitFor(() => expect(api.renderAICodingOutput).toHaveBeenCalledWith({
      target: 'docx',
      model_output: '{"title":"Demo","blocks":[]}',
      original_filename: undefined,
      slides: undefined
    }));
    expect(screen.getByText('格式检查 96')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /下载/ }));
    await waitFor(() => expect(fileService.downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'aicoding-generated.docx'));
  });

  it('renders settings and config pages', async () => {
    const { rerender } = renderWithProviders(<Settings />);
    expect(await screen.findAllByText('stub')).toHaveLength(2);

    rerender(<NGA />);
    expect(screen.getByLabelText('档案名称')).toBeInTheDocument();

    expect(screen.getByLabelText('Endpoint')).toBeInTheDocument();
  });

  it('renders design page wrappers', async () => {
    const { rerender } = renderWithProviders(<Charts />);
    expect(screen.getByPlaceholderText('数据说明')).toBeInTheDocument();

    rerender(<Colors />);
    await waitFor(() => expect(api.getColorSchemes).toHaveBeenCalled());
    expect(screen.getByText('自定义')).toBeInTheDocument();

    rerender(<SmartArt />);
    await waitFor(() => expect(api.getSmartArtTypes).toHaveBeenCalled());
    expect(screen.getByLabelText('节点')).toBeInTheDocument();

    rerender(<Templates />);
    expect(screen.getByPlaceholderText('模板名称')).toBeInTheDocument();
  });
});
