import { fireEvent, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/render';
import FileUpload from './FileUpload';
import GenerateForm from './GenerateForm';
import GenerationHistory from './GenerationHistory';
import ProgressBar from './ProgressBar';
import ResultPreview from './ResultPreview';

describe('document generator components', () => {
  it('renders upload state and removes selected files', () => {
    const onChange = vi.fn();
    const file = new File(['# Demo'], 'input.md', { type: 'text/markdown' });

    renderWithProviders(<FileUpload file={file} onChange={onChange} />);

    expect(screen.getByText('input.md')).toBeInTheDocument();
    fireEvent.click(screen.getByTitle('删除文件'));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it('submits generation and exposes options', () => {
    const onSubmit = vi.fn();
    const onChange = vi.fn();

    renderWithProviders(
      <GenerateForm
        target="pptx"
        slides={8}
        templates={[{ template_id: 'tpl', name: 'Template', category: 'business', description: 'Demo', is_system: true }]}
        colorSchemes={[{
          scheme_id: 'scheme',
          name: 'Scheme',
          category: 'business',
          primary_color: '#111111',
          secondary_color: '#222222',
          accent_color: '#333333',
          background_color: '#FFFFFF',
          text_color: '#000000',
          is_system: true
        }]}
        users={[{
          user_id: 'user',
          user_name: 'User',
          nga_endpoint: 'http://example.test/v1',
          auth_token: '***HIDDEN***',
          llm_provider: 'nga',
          llm_model: 'glm-4.7',
          ppt_renderer: 'stub'
        }]}
        loading={false}
        onChange={onChange}
        onSubmit={onSubmit}
      />
    );

    expect(screen.getByText('PPTX')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('generate-submit'));
    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it('renders progress states', () => {
    const { rerender } = renderWithProviders(<ProgressBar progress={null} />);
    expect(screen.queryByText('completed')).not.toBeInTheDocument();

    rerender(<ProgressBar progress={{ task_id: 'task', status: 'completed', progress: 100, current_step: '生成完成' }} />);
    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.getByText('生成完成')).toBeInTheDocument();

    rerender(<ProgressBar progress={{ task_id: 'task', status: 'failed', progress: 0, current_step: '失败', error: 'boom' }} />);
    expect(screen.getByText('boom')).toBeInTheDocument();
  });

  it('renders downloadable result only after completion', () => {
    const onDownload = vi.fn();
    const { rerender } = renderWithProviders(<ResultPreview progress={null} onDownload={onDownload} />);
    expect(screen.queryByText('下载')).not.toBeInTheDocument();

    rerender(<ResultPreview progress={{ task_id: 'task', status: 'completed', progress: 100, current_step: 'done' }} onDownload={onDownload} />);
    fireEvent.click(screen.getByRole('button', { name: /下载/ }));
    expect(onDownload).toHaveBeenCalledOnce();

    rerender(<ResultPreview progress={{ task_id: 'task', status: 'failed', progress: 0, current_step: 'failed', friendly_error: '模型连接失败', error: 'timeout' }} onDownload={onDownload} />);
    expect(screen.getByText('模型连接失败')).toBeInTheDocument();
  });

  it('renders generation history empty states and row actions', () => {
    const onRefresh = vi.fn();
    const onDownload = vi.fn();
    const onReuse = vi.fn();
    const onDelete = vi.fn();
    const completed = {
      task_id: 'completed-task',
      status: 'completed',
      progress: 100,
      current_step: 'done',
      metadata: {
        original_filename: 'source.md',
        target: 'docx',
        slides: 5,
        template_id: 'tpl',
        color_scheme_id: 'scheme',
        updated_at: '2026-07-06T01:02:03Z'
      }
    };
    const fallback = {
      task_id: 'fallback-task',
      status: 'mystery',
      progress: 0,
      current_step: 'unknown',
      metadata: {}
    };

    const { rerender } = renderWithProviders(<GenerationHistory tasks={[]} onRefresh={onRefresh} />);
    expect(screen.getByText('还没有生成记录')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /刷新/ }));
    expect(onRefresh).toHaveBeenCalledOnce();

    rerender(
      <GenerationHistory
        tasks={[completed, fallback]}
        onRefresh={onRefresh}
        onDownload={onDownload}
        onReuse={onReuse}
        onDelete={onDelete}
      />
    );

    expect(screen.getByText('source.md')).toBeInTheDocument();
    expect(screen.getByText('未命名输入')).toBeInTheDocument();
    expect(screen.getByText('5 页 · tpl · scheme')).toBeInTheDocument();
    expect(screen.getByText('- 页 · 默认模板 · 默认配色')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('下载 completed-task'));
    fireEvent.click(screen.getByLabelText('复用 fallback-task'));
    fireEvent.click(screen.getByLabelText('删除 fallback-task'));

    expect(onDownload).toHaveBeenCalledWith(completed);
    expect(onReuse).toHaveBeenCalledWith(fallback);
    expect(onDelete).toHaveBeenCalledWith(fallback);
    expect(screen.getByLabelText('下载 fallback-task')).toBeDisabled();
  });
});
