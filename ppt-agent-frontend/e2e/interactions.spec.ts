import { expect, test } from '@playwright/test';
import path from 'node:path';

function collectConsoleErrors(page: import('@playwright/test').Page) {
  const errors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') {
      errors.push(message.text());
    }
  });
  return errors;
}

test('creates, tests, lists, and switches a model profile', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  const userName = `E2E User ${Date.now()}`;

  await page.goto('/config/nga');
  await page.getByLabel('档案名称').fill(userName);
  await page.getByLabel('Endpoint').fill('http://e2e.example.test/v1');
  await page.getByLabel('Token').fill('e2e-token');
  await page.getByLabel('模型').fill('glm-4.7');

  await page.getByTestId('user-test-connection').click();
  await expect(page.getByText(/配置格式有效/)).toBeVisible();

  await page.getByTestId('user-save').click();
  await expect(page.getByText('模型配置档案已保存')).toBeVisible();
  await expect(page.getByRole('row', { name: new RegExp(userName) })).toBeVisible();
  await expect(page.getByRole('row', { name: new RegExp(userName) })).toContainText('***HIDDEN***');

  await page.getByLabel(`使用 ${userName}`).click();
  await expect(page.getByText('已使用该模型档案')).toBeVisible();
  await expect(page.getByText(userName).first()).toBeVisible();

  expect(consoleErrors).toEqual([]);
});

test('exports and imports configuration from settings', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);

  await page.goto('/config/settings');
  const downloadPromise = page.waitForEvent('download');
  await page.getByTestId('config-export').click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('ppt-agent-config.json');

  await page.locator('input[type="file"]').setInputFiles(path.join(import.meta.dirname, 'fixtures/config-import.json'));
  await expect(page.getByText(/导入完成/)).toBeVisible();

  expect(consoleErrors).toEqual([]);
});

test('imports a custom template through the template center', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  const templateName = `E2E Template ${Date.now()}`;

  await page.goto('/design/templates');
  await page.getByPlaceholder('模板名称').fill(templateName);
  await page.locator('input[type="file"]').setInputFiles(path.join(import.meta.dirname, '../../templates/company_template.pptx'));
  await expect(page.getByText('company_template.pptx')).toBeVisible();
  await page.getByTestId('template-import').click();

  await expect(page.getByText('已导入')).toBeVisible();
  await expect(page.getByRole('cell', { name: templateName, exact: true })).toBeVisible();

  expect(consoleErrors).toEqual([]);
});

test('recommends and creates a color scheme', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);
  const schemeName = `E2E Scheme ${Date.now()}`;

  await page.goto('/design/colors');
  await page.getByTestId('color-recommend').click();
  await expect(page.getByTestId('color-recommendation')).toContainText(/\S+/);

  await page.getByPlaceholder('名称').fill(schemeName);
  await page.getByPlaceholder('分类').fill('business');
  await page.getByPlaceholder('#123456').fill('#123456');
  await page.getByPlaceholder('#234567').fill('#234567');
  await page.getByPlaceholder('#345678').fill('#345678');
  await page.getByTestId('color-save').click();

  await expect(page.getByText('已创建')).toBeVisible();
  await expect(page.getByRole('cell', { name: schemeName, exact: true })).toBeVisible();

  expect(consoleErrors).toEqual([]);
});

test('generates chart and SmartArt IR from design pages', async ({ page }) => {
  const consoleErrors = collectConsoleErrors(page);

  await page.goto('/design/charts');
  await page.getByPlaceholder('数据说明').fill('monthly sales comparison');
  await page.getByTestId('chart-recommend').click();
  await expect(page.getByTestId('chart-generate')).toBeVisible();
  await page.getByTestId('chart-generate').click();
  await expect(page.locator('.json-panel')).toContainText('"chart_type"');

  await page.goto('/design/smartart');
  await page.getByTestId('smartart-generate').click();
  await expect(page.locator('.json-panel')).toContainText('"layout": "horizontal"');

  expect(consoleErrors).toEqual([]);
});
