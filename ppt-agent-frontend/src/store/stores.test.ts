import { afterEach, describe, expect, it } from 'vitest';
import { useDocumentStore, useTemplateStore, useUIStore, useUserStore } from './index';
import type { ColorScheme, TemplateConfig, UserConfig } from '@/types';

afterEach(() => {
  useDocumentStore.setState({ taskId: null, progress: null });
  useTemplateStore.setState({ templates: [], colorSchemes: [] });
  useUIStore.setState({ collapsed: false });
  useUserStore.setState({ currentUser: null, users: [], currentTemplate: null, currentColorScheme: null });
  localStorage.clear();
});

it('updates document progress state', () => {
  useDocumentStore.getState().setTaskId('task-1');
  useDocumentStore.getState().setProgress({ task_id: 'task-1', status: 'completed', progress: 100, current_step: 'done' });

  expect(useDocumentStore.getState().taskId).toBe('task-1');
  expect(useDocumentStore.getState().progress?.status).toBe('completed');
});

it('updates template and color stores', () => {
  const template: TemplateConfig = {
    template_id: 'tpl',
    name: 'Template',
    category: 'business',
    description: 'Demo',
    is_system: true
  };
  const scheme: ColorScheme = {
    scheme_id: 'scheme',
    name: 'Scheme',
    category: 'business',
    primary_color: '#111111',
    secondary_color: '#222222',
    accent_color: '#333333',
    background_color: '#FFFFFF',
    text_color: '#000000',
    is_system: true
  };

  useTemplateStore.getState().setTemplates([template]);
  useTemplateStore.getState().setColorSchemes([scheme]);

  expect(useTemplateStore.getState().templates).toEqual([template]);
  expect(useTemplateStore.getState().colorSchemes).toEqual([scheme]);
});

it('updates UI collapsed state', () => {
  useUIStore.getState().setCollapsed(true);
  expect(useUIStore.getState().collapsed).toBe(true);
});

it('persists user selections', () => {
  const user: UserConfig = {
    user_id: 'user',
    user_name: 'User',
    nga_endpoint: 'http://example.test/v1',
    auth_token: '***HIDDEN***',
    llm_provider: 'nga',
    llm_model: 'glm-4.7',
    ppt_renderer: 'stub'
  };
  const template: TemplateConfig = { template_id: 'tpl', name: 'Template', category: 'business', description: 'Demo', is_system: true };
  const color: ColorScheme = {
    scheme_id: 'scheme',
    name: 'Scheme',
    category: 'business',
    primary_color: '#111111',
    secondary_color: '#222222',
    accent_color: '#333333',
    background_color: '#FFFFFF',
    text_color: '#000000',
    is_system: true
  };

  useUserStore.getState().setUsers([user]);
  useUserStore.getState().setCurrentUser(user);
  useUserStore.getState().setCurrentTemplate(template);
  useUserStore.getState().setCurrentColorScheme(color);

  expect(useUserStore.getState().users).toHaveLength(1);
  expect(useUserStore.getState().currentUser?.user_name).toBe('User');
  expect(useUserStore.getState().currentTemplate?.template_id).toBe('tpl');
  expect(useUserStore.getState().currentColorScheme?.scheme_id).toBe('scheme');
  expect(localStorage.getItem('ppt-agent-user-storage')).toContain('User');
});

describe('store barrel exports', () => {
  it('exposes all store hooks from index', () => {
    expect(useDocumentStore).toBeTypeOf('function');
    expect(useTemplateStore).toBeTypeOf('function');
    expect(useUIStore).toBeTypeOf('function');
    expect(useUserStore).toBeTypeOf('function');
  });
});
