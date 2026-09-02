import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/render';
import ChartDesigner from './ChartDesigner';
import SmartArtEditor from './SmartArtEditor';

const api = vi.hoisted(() => ({
  recommendChart: vi.fn(),
  generateChart: vi.fn(),
  getSmartArtTypes: vi.fn(),
  generateSmartArt: vi.fn()
}));

vi.mock('@/services/api', () => ({ apiClient: api }));

describe('design system components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('recommends and generates chart IR', async () => {
    api.recommendChart.mockResolvedValueOnce({
      recommendation: {
        chart_type: 'line',
        confidence: 0.9,
        reason: '趋势',
        data_requirements: [],
        styling_tips: []
      }
    });
    api.generateChart.mockResolvedValueOnce({ chart: { chart_type: 'line', title: '示例图表' } });

    renderWithProviders(<ChartDesigner />);
    fireEvent.change(screen.getByPlaceholderText('数据说明'), { target: { value: 'monthly trend' } });
    fireEvent.click(screen.getByTestId('chart-recommend'));

    await screen.findByText('趋势');
    fireEvent.click(screen.getByTestId('chart-generate'));

    await waitFor(() => expect(api.generateChart).toHaveBeenCalledWith(expect.objectContaining({ chart_type: 'line' })));
    expect(screen.getByText(/"chart_type": "line"/)).toBeInTheDocument();
  });

  it('loads SmartArt types and generates IR', async () => {
    api.getSmartArtTypes.mockResolvedValueOnce({ types: ['process', 'hierarchy'] });
    api.generateSmartArt.mockResolvedValueOnce({ smartart: { layout: 'horizontal', type: 'process' } });

    renderWithProviders(<SmartArtEditor />);
    await waitFor(() => expect(api.getSmartArtTypes).toHaveBeenCalledOnce());
    fireEvent.click(screen.getByTestId('smartart-generate'));

    await waitFor(() => expect(api.generateSmartArt).toHaveBeenCalledWith({
      nodes: [
        { id: 'n1', text: '调研', level: 0 },
        { id: 'n2', text: '规划', level: 0 },
        { id: 'n3', text: '生成', level: 0 },
        { id: 'n4', text: '交付', level: 0 }
      ],
      config: { smartart_type: 'process' }
    }));
    expect(screen.getByText(/"layout": "horizontal"/)).toBeInTheDocument();
  });
});
