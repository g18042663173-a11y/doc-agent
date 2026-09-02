import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/render';
import ConfigImportExport from './ConfigImportExport';
import NGAConfigForm from './NGAConfigForm';
import UserList from './UserList';

const api = vi.hoisted(() => ({
  exportConfig: vi.fn(),
  importConfig: vi.fn(),
  testConnection: vi.fn(),
  createUser: vi.fn(),
  getUsers: vi.fn(),
  switchUser: vi.fn(),
  deleteUser: vi.fn()
}));

const files = vi.hoisted(() => ({
  downloadJson: vi.fn(),
  readJsonFile: vi.fn()
}));

vi.mock('@/services/api', () => ({ apiClient: api, getApiErrorMessage: (_error: unknown, fallback?: string) => fallback || 'api error' }));
vi.mock('@/services/fileService', () => files);

describe('config manager components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getUsers.mockResolvedValue({ users: [] });
  });

  it('exports and imports configuration', async () => {
    const onImported = vi.fn();
    api.exportConfig.mockResolvedValueOnce({ exported_at: 'now', users: [] });
    files.readJsonFile.mockResolvedValueOnce({ users: [{ user_id: 'u1' }], templates: [{ template_id: 't1' }], color_schemes: [{ scheme_id: 'c1' }] });
    api.importConfig.mockResolvedValueOnce({ success: true, imported_users: 1 });

    const { container } = renderWithProviders(<ConfigImportExport onImported={onImported} />);

    fireEvent.click(screen.getByTestId('config-export'));
    await waitFor(() => expect(files.downloadJson).toHaveBeenCalledWith({ exported_at: 'now', users: [] }, 'ppt-agent-config.json'));

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(['{}'], 'config.json', { type: 'application/json' })] } });

    await waitFor(() => expect(api.importConfig).toHaveBeenCalledWith({
      users: [{ user_id: 'u1' }],
      templates: [{ template_id: 't1' }],
      color_schemes: [{ scheme_id: 'c1' }]
    }));
    expect(onImported).toHaveBeenCalledOnce();
  });

  it('shows import errors for invalid config files', async () => {
    files.readJsonFile.mockRejectedValueOnce(new Error('invalid json'));
    const { container } = renderWithProviders(<ConfigImportExport />);

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(['bad'], 'config.json', { type: 'application/json' })] } });

    await waitFor(() => expect(files.readJsonFile).toHaveBeenCalled());
    expect(api.importConfig).not.toHaveBeenCalled();
  });

  it('tests and saves a model profile', async () => {
    const onSaved = vi.fn();
    api.testConnection.mockResolvedValueOnce({ success: true, message: 'ok' });
    api.createUser.mockResolvedValueOnce({ success: true, user_id: 'u1' });

    renderWithProviders(<NGAConfigForm onSaved={onSaved} />);

    fireEvent.change(screen.getByLabelText('档案名称'), { target: { value: 'User' } });
    fireEvent.change(screen.getByLabelText('Endpoint'), { target: { value: 'http://example.test/v1' } });
    fireEvent.change(screen.getByLabelText('Token'), { target: { value: 'secret' } });
    fireEvent.change(screen.getByLabelText('模型'), { target: { value: 'glm-4.7' } });
    fireEvent.click(screen.getByTestId('user-test-connection'));
    await waitFor(() => expect(api.testConnection).toHaveBeenCalledWith('http://example.test/v1', 'secret'));

    fireEvent.click(screen.getByTestId('user-save'));
    await waitFor(() => expect(api.createUser).toHaveBeenCalledWith({
      user_name: 'User',
      nga_endpoint: 'http://example.test/v1',
      auth_token: 'secret',
      llm_provider: 'nga',
      llm_model: 'glm-4.7',
      ppt_renderer: 'stub'
    }));
    expect(onSaved).toHaveBeenCalledOnce();
  });

  it('handles failed connection tests and default model fallback', async () => {
    api.testConnection.mockResolvedValueOnce({ success: false, message: 'bad endpoint' });
    api.createUser.mockResolvedValueOnce({ success: true, user_id: 'u2' });

    renderWithProviders(<NGAConfigForm />);

    fireEvent.change(screen.getByLabelText('档案名称'), { target: { value: 'Fallback User' } });
    fireEvent.change(screen.getByLabelText('Endpoint'), { target: { value: 'http://example.test/v1' } });
    fireEvent.change(screen.getByLabelText('Token'), { target: { value: 'secret' } });
    fireEvent.change(screen.getByLabelText('模型'), { target: { value: '' } });
    fireEvent.click(screen.getByTestId('user-test-connection'));
    await waitFor(() => expect(api.testConnection).toHaveBeenCalled());

    fireEvent.click(screen.getByTestId('user-save'));
    await waitFor(() => expect(api.createUser).toHaveBeenCalledWith(expect.objectContaining({ llm_model: 'glm-4.7' })));
  });

  it('loads, switches, and deletes users', async () => {
    const user = {
      user_id: 'u1',
      user_name: 'User',
      nga_endpoint: 'http://example.test/v1',
      auth_token: '***HIDDEN***',
      llm_provider: 'nga',
      llm_model: 'glm-4.7',
      ppt_renderer: 'stub'
    };
    api.getUsers.mockResolvedValue({ users: [user] });
    api.switchUser.mockResolvedValueOnce(user);
    api.deleteUser.mockResolvedValueOnce({ success: true });

    renderWithProviders(<UserList refreshToken={1} />);

    await screen.findByText('User');
    fireEvent.click(screen.getByLabelText('使用 User'));
    await waitFor(() => expect(api.switchUser).toHaveBeenCalledWith('u1'));

    fireEvent.click(screen.getByLabelText('删除 User'));
    await waitFor(() => expect(api.deleteUser).toHaveBeenCalledWith('u1'));
  });
});
