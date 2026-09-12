import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, type InitialEntry } from 'react-router-dom';
import { renderWithProviders } from '@/test/render';
import { useDocumentStore } from '@/store';
import SmartGenerate from './Smart';

const api = vi.hoisted(() => ({
  getTemplates: vi.fn(),
  getColorSchemes: vi.fn(),
  getUsers: vi.fn(),
  startGeneration: vi.fn(),
  getProgress: vi.fn(),
  downloadFile: vi.fn(),
  getGenerationHistory: vi.fn(),
  deleteGenerationHistory: vi.fn(),
  getSystemHealth: vi.fn()
}));

const files = vi.hoisted(() => ({
  downloadBlob: vi.fn()
}));

const sockets = vi.hoisted(() => ({
  connectProgressSocket: vi.fn()
}));

vi.mock('@/services/api', () => ({ apiClient: api, getApiErrorMessage: (_error: unknown, fallback?: string) => fallback || 'api error' }));
vi.mock('@/services/fileService', () => files);
vi.mock('@/services/websocket', () => sockets);

function renderSmart(initialEntries: InitialEntry[] = ['/generate/smart']) {
  return renderWithProviders(
    <MemoryRouter initialEntries={initialEntries}>
      <SmartGenerate />
    </MemoryRouter>
  );
}

describe('SmartGenerate page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useDocumentStore.setState({ taskId: null, progress: null });
    api.getTemplates.mockResolvedValue({ templates: [{ template_id: 'tpl', name: 'Template', category: 'business', description: 'Demo', is_system: true }] });
    api.getColorSchemes.mockResolvedValue({ schemes: [{ scheme_id: 'scheme', name: 'Scheme', category: 'business' }] });
    api.getUsers.mockResolvedValue({ users: [{ user_id: 'user', user_name: 'User' }] });
    api.getGenerationHistory.mockResolvedValue({ tasks: [] });
    api.deleteGenerationHistory.mockResolvedValue({ success: true });
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
    sockets.connectProgressSocket.mockImplementation((_taskId, options) => {
      options.onMessage({ task_id: 'task', status: 'completed', progress: 100, current_step: 'done' });
      return { close: vi.fn() };
    });
  });

  it('loads generation options and starts a WebSocket-backed task', async () => {
    api.startGeneration.mockResolvedValueOnce({ task_id: 'task', status: 'processing', message: 'started' });
    const { container } = renderSmart();

    await waitFor(() => expect(api.getTemplates).toHaveBeenCalled());
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(['# Demo'], 'input.md', { type: 'text/markdown' })] } });
    fireEvent.click(screen.getByTestId('generate-submit'));

    await waitFor(() => expect(api.startGeneration).toHaveBeenCalledWith(expect.any(File), expect.objectContaining({ target: 'pptx', slides: 8 })));
    expect(sockets.connectProgressSocket).toHaveBeenCalledWith('task', expect.objectContaining({ onMessage: expect.any(Function), onError: expect.any(Function) }));
    expect(await screen.findByText('completed')).toBeInTheDocument();
  });

  it('does not start without a file and handles start failures', async () => {
    api.startGeneration.mockRejectedValueOnce(new Error('failed'));
    const { container } = renderSmart();
    await waitFor(() => expect(api.getUsers).toHaveBeenCalled());

    fireEvent.click(screen.getByTestId('generate-submit'));
    expect(api.startGeneration).not.toHaveBeenCalled();

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(['# Demo'], 'input.md', { type: 'text/markdown' })] } });
    fireEvent.click(screen.getByTestId('generate-submit'));
    await waitFor(() => expect(api.startGeneration).toHaveBeenCalled());
  });

  it('falls back to polling and downloads completed results', async () => {
    api.startGeneration.mockResolvedValueOnce({ task_id: 'task', status: 'processing', message: 'started' });
    api.getProgress.mockResolvedValueOnce({ task_id: 'task', status: 'completed', progress: 100, current_step: 'done' });
    api.downloadFile.mockResolvedValueOnce(new Blob(['pptx']));
    sockets.connectProgressSocket.mockImplementation((_taskId, options) => {
      options.onError();
      return { close: vi.fn() };
    });

    const { container } = renderSmart();
    await waitFor(() => expect(api.getTemplates).toHaveBeenCalled());
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(['# Demo'], 'input.md', { type: 'text/markdown' })] } });
    fireEvent.click(screen.getByTestId('generate-submit'));

    await screen.findByText('completed');
    fireEvent.click(screen.getByRole('button', { name: /下载/ }));
    await waitFor(() => expect(files.downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'generated.pptx'));
  });

  it('uses DOCX download names for DOCX targets', async () => {
    useDocumentStore.getState().setProgress({ task_id: 'task', status: 'completed', progress: 100, current_step: 'done' });
    api.downloadFile.mockResolvedValueOnce(new Blob(['docx']));

    renderSmart();
    fireEvent.mouseDown(screen.getByText('PPTX'));
    fireEvent.click(await screen.findByText('DOCX'));
    fireEvent.click(screen.getByRole('button', { name: /下载/ }));

    await waitFor(() => expect(files.downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'generated.docx'));
  });

  it('applies reused parameters from dashboard route state', async () => {
    useDocumentStore.getState().setProgress({ task_id: 'task', status: 'completed', progress: 100, current_step: 'done' });
    api.downloadFile.mockResolvedValueOnce(new Blob(['docx']));

    renderSmart([{
      pathname: '/generate/smart',
      state: {
        task: {
          task_id: 'history-task',
          status: 'completed',
          progress: 100,
          current_step: 'done',
          metadata: {
            target: 'docx',
            slides: 5,
            template_id: 'tpl',
            color_scheme_id: 'scheme',
            user_id: 'user'
          }
        }
      }
    }]);

    await screen.findByText('DOCX');
    fireEvent.click(screen.getByRole('button', { name: /下载/ }));

    await waitFor(() => expect(files.downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'generated.docx'));
  });
});
