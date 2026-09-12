import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/render';
import ColorPicker from './ColorPicker';
import TemplateGallery from './TemplateGallery';

const api = vi.hoisted(() => ({
  getColorSchemes: vi.fn(),
  recommendColors: vi.fn(),
  createColorScheme: vi.fn(),
  getTemplates: vi.fn(),
  importTemplate: vi.fn()
}));

vi.mock('@/services/api', () => ({ apiClient: api, getApiErrorMessage: (_error: unknown, fallback?: string) => fallback || 'api error' }));

describe('design collection components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads, recommends, and creates color schemes', async () => {
    api.getColorSchemes.mockResolvedValue({
      schemes: [{
        scheme_id: 'business_blue',
        name: '商务蓝',
        category: 'business',
        primary_color: '#111111',
        secondary_color: '#222222',
        accent_color: '#333333',
        background_color: '#FFFFFF',
        text_color: '#000000',
        is_system: true
      }]
    });
    api.recommendColors.mockResolvedValueOnce({ recommendations: [{ scheme_id: 'business_blue', confidence: 0.9, reason: 'fit' }] });
    api.createColorScheme.mockResolvedValueOnce({ success: true, scheme_id: 'custom' });

    renderWithProviders(<ColorPicker />);

    await screen.findByText('商务蓝');
    fireEvent.click(screen.getByTestId('color-recommend'));
    await expect(screen.findByTestId('color-recommendation')).resolves.toHaveTextContent('business_blue');

    fireEvent.change(screen.getByPlaceholderText('名称'), { target: { value: 'Custom' } });
    fireEvent.change(screen.getByPlaceholderText('分类'), { target: { value: 'business' } });
    fireEvent.change(screen.getByPlaceholderText('#123456'), { target: { value: '#123456' } });
    fireEvent.change(screen.getByPlaceholderText('#234567'), { target: { value: '#234567' } });
    fireEvent.change(screen.getByPlaceholderText('#345678'), { target: { value: '#345678' } });
    fireEvent.click(screen.getByTestId('color-save'));

    await waitFor(() => expect(api.createColorScheme).toHaveBeenCalledWith(expect.objectContaining({ name: 'Custom', category: 'business' })));
  });

  it('handles empty color recommendations', async () => {
    api.getColorSchemes.mockResolvedValue({ schemes: [] });
    api.recommendColors.mockResolvedValueOnce({ recommendations: [] });

    renderWithProviders(<ColorPicker />);
    fireEvent.click(screen.getByTestId('color-recommend'));

    await waitFor(() => expect(api.recommendColors).toHaveBeenCalledWith('商务报告'));
    expect(screen.queryByTestId('color-recommendation')).not.toBeInTheDocument();
  });

  it('loads templates and imports a selected PPTX', async () => {
    api.getTemplates.mockResolvedValue({
      templates: [{ template_id: 'tpl', name: '商务报告模板', category: 'business', description: 'Demo', is_system: true }]
    });
    api.importTemplate.mockResolvedValueOnce({ success: true, template_id: 'custom' });

    const { container } = renderWithProviders(<TemplateGallery />);

    await screen.findByText('商务报告模板');
    fireEvent.change(screen.getByPlaceholderText('模板名称'), { target: { value: 'Imported' } });

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(['pptx'], 'template.pptx')] } });
    fireEvent.click(screen.getByTestId('template-import'));

    await waitFor(() => expect(api.importTemplate).toHaveBeenCalledWith(expect.any(File), 'Imported', 'business'));
  });

  it('keeps template import disabled until both name and file are present', async () => {
    api.getTemplates.mockResolvedValue({ templates: [] });
    renderWithProviders(<TemplateGallery />);

    expect(screen.getByTestId('template-import')).toBeDisabled();
    fireEvent.click(screen.getByTestId('template-import'));
    expect(api.importTemplate).not.toHaveBeenCalled();
  });
});
