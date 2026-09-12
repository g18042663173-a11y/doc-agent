import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { renderWithProviders } from '@/test/render';
import { useUIStore, useUserStore } from '@/store';
import AppHeader from './Header';
import MainLayout from './MainLayout';
import Sidebar from './Sidebar';

const api = vi.hoisted(() => ({
  getUsers: vi.fn(),
  getTemplates: vi.fn(),
  getColorSchemes: vi.fn(),
  switchUser: vi.fn()
}));

vi.mock('@/services/api', () => ({ apiClient: api }));

describe('layout components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useUIStore.setState({ collapsed: false });
    useUserStore.setState({ users: [], currentUser: null });
    api.getUsers.mockResolvedValue({ users: [{ user_id: 'u1', user_name: 'User' }] });
    api.getTemplates.mockResolvedValue({ templates: [] });
    api.getColorSchemes.mockResolvedValue({ schemes: [] });
  });

  it('refreshes shell data and toggles navigation', async () => {
    renderWithProviders(
      <MemoryRouter>
        <AppHeader />
      </MemoryRouter>
    );

    await waitFor(() => expect(api.getUsers).toHaveBeenCalled());
    fireEvent.click(screen.getByLabelText('切换导航'));
    expect(useUIStore.getState().collapsed).toBe(true);
    fireEvent.click(screen.getByLabelText('刷新'));
    await waitFor(() => expect(api.getTemplates).toHaveBeenCalledTimes(2));
  });

  it('clears the selected user in the header', async () => {
    const user = { user_id: 'u1', user_name: 'User' };
    api.getUsers.mockResolvedValue({ users: [user] });
    useUserStore.getState().setUsers([user as never]);
    useUserStore.getState().setCurrentUser(user as never);

    renderWithProviders(
      <MemoryRouter>
        <AppHeader />
      </MemoryRouter>
    );

    await screen.findByText('User');
    const clearControl = screen.getByLabelText('close-circle').closest('.ant-select-clear') as HTMLElement;
    fireEvent.mouseDown(clearControl);
    fireEvent.click(clearControl);
    await waitFor(() => expect(useUserStore.getState().currentUser).toBeNull());
  });

  it('renders mobile sidebar navigation and main outlet', () => {
    renderWithProviders(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/dashboard" element={<div>Dashboard Outlet</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('PPT Agent')).toBeInTheDocument();
    expect(screen.getByText('Dashboard Outlet')).toBeInTheDocument();
  });

  it('navigates when sidebar items are clicked', async () => {
    renderWithProviders(
      <MemoryRouter initialEntries={['/export']}>
        <Routes>
          <Route path="/dashboard" element={<><Sidebar /><div>Dashboard</div></>} />
          <Route path="/export" element={<><Sidebar /><div>Export Page</div></>} />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByText('仪表板'));
    expect(await screen.findByText('Dashboard')).toBeInTheDocument();
  });
});
