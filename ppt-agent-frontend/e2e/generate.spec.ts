import { expect, test } from '@playwright/test';
import { stat } from 'node:fs/promises';
import path from 'node:path';

test('uploads markdown, generates PPTX, and downloads the result', async ({ page }, testInfo) => {
  const consoleErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') {
      consoleErrors.push(message.text());
    }
  });

  await page.goto('/generate/smart');
  await expect(page.getByText('上传 md / docx / pptx / xlsx / xlsm')).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles(path.join(import.meta.dirname, 'fixtures/input.md'));
  await expect(page.getByText('input.md')).toBeVisible();

  await page.getByTestId('generate-submit').click();

  await expect(page.getByText('completed').first()).toBeVisible({ timeout: 45_000 });
  const downloadButton = page.locator('.ant-card').filter({ hasText: '结果下载' }).getByRole('button', { name: /下载/ });
  await expect(downloadButton).toBeVisible();

  const downloadPromise = page.waitForEvent('download');
  await downloadButton.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('generated.pptx');

  const outputPath = testInfo.outputPath(download.suggestedFilename());
  await download.saveAs(outputPath);
  await expect(async () => {
    const output = await stat(outputPath);
    expect(output.size).toBeGreaterThan(0);
  }).toPass();

  expect(consoleErrors).toEqual([]);
});

test('bridges AICoding prompt, pasted WordIR, and DOCX download', async ({ page }, testInfo) => {
  const consoleErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') {
      consoleErrors.push(message.text());
    }
  });

  await page.goto('/generate/aicoding');
  await expect(page.getByText('AICoding prompt')).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles(path.join(import.meta.dirname, 'fixtures/input.md'));
  await expect(page.getByText('input.md')).toBeVisible();
  await page.getByTestId('aicoding-prompt').click();
  await expect(page.getByTestId('aicoding-prompt-text')).toHaveValue(/WordIR/);

  const wordIr = {
    title: 'AICoding E2E Word',
    subtitle: 'Manual bridge',
    blocks: [
      { type: 'heading', text: '一、验证结论', level: 1 },
      { type: 'paragraph', text: 'AICoding 手动桥接可以生成 WordIR 并下载 DOCX。' },
      { type: 'table', table_headers: ['项目', '状态'], table_rows: [['Prompt', '完成'], ['DOCX', '完成']] }
    ]
  };
  await page.getByTestId('aicoding-json').fill(JSON.stringify(wordIr));
  await page.getByTestId('aicoding-render').click();

  await expect(page.getByText('格式检查')).toBeVisible({ timeout: 30_000 });
  const downloadButton = page.locator('.ant-card').filter({ hasText: '结果下载' }).getByRole('button', { name: /下载/ });
  const downloadPromise = page.waitForEvent('download');
  await downloadButton.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('aicoding-generated.docx');

  const outputPath = testInfo.outputPath(download.suggestedFilename());
  await download.saveAs(outputPath);
  await expect(async () => {
    const output = await stat(outputPath);
    expect(output.size).toBeGreaterThan(0);
  }).toPass();

  expect(consoleErrors).toEqual([]);
});
