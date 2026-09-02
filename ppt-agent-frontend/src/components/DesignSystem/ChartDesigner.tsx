import { Button, Card, Form, Input, Select, Space, Typography } from 'antd';
import { useState } from 'react';
import { apiClient } from '@/services/api';
import type { ChartRecommendation } from '@/types';

export default function ChartDesigner() {
  const [recommendation, setRecommendation] = useState<ChartRecommendation | null>(null);
  const [chartIR, setChartIR] = useState<Record<string, unknown> | null>(null);

  const recommend = async (values: { data_description: string; data_type: string; purpose: string }) => {
    const data = await apiClient.recommendChart(values.data_description, {
      data_type: values.data_type,
      purpose: values.purpose
    });
    setRecommendation(data.recommendation);
  };

  const generate = async () => {
    const chartType = recommendation?.chart_type || 'bar';
    const data = await apiClient.generateChart({
      chart_type: chartType,
      title: '示例图表',
      data: { labels: ['A', 'B'], datasets: [{ name: '数值', data: [12, 18] }] }
    });
    setChartIR(data.chart);
  };

  return (
    <Space orientation="vertical" size={16} className="wide">
      <Card size="small">
        <Form layout="inline" onFinish={recommend}>
          <Form.Item name="data_description" rules={[{ required: true }]}><Input placeholder="数据说明" /></Form.Item>
          <Form.Item name="data_type" initialValue="categorical">
            <Select style={{ width: 150 }} options={[
              { value: 'categorical', label: 'categorical' },
              { value: 'time_series', label: 'time_series' },
              { value: 'numeric', label: 'numeric' }
            ]} />
          </Form.Item>
          <Form.Item name="purpose" initialValue="comparison">
            <Select style={{ width: 140 }} options={[
              { value: 'comparison', label: 'comparison' },
              { value: 'trend', label: 'trend' },
              { value: 'composition', label: 'composition' }
            ]} />
          </Form.Item>
          <Button htmlType="submit" data-testid="chart-recommend">推荐</Button>
        </Form>
      </Card>
      {recommendation && (
        <Card size="small" title={recommendation.chart_type}>
          <Space orientation="vertical">
            <Typography.Text>{recommendation.reason}</Typography.Text>
            <Button type="primary" onClick={generate} data-testid="chart-generate">生成 IR</Button>
          </Space>
        </Card>
      )}
      {chartIR && <pre className="json-panel">{JSON.stringify(chartIR, null, 2)}</pre>}
    </Space>
  );
}
