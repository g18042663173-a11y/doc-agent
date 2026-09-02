import { expect, test } from '@playwright/test';

const routes = [
  { path: '/dashboard', text: '模板库' },
  { path: '/generate/smart', text: '上传 md / docx / pptx / xlsx / xlsm' },
  { path: '/generate/aicoding', text: 'AICoding prompt' },
  { path: '/config/nga', text: 'Endpoint' },
  { path: '/design/templates', text: '选择 PPTX' },
  { path: '/design/colors', text: '自定义' },
  { path: '/design/charts', placeholder: '数据说明' },
  { path: '/design/smartart', text: '节点' },
  { path: '/config/settings', text: '导出个人配置' }
];

const viewports = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile', width: 390, height: 844 }
];

for (const viewport of viewports) {
  test(`core pages load quickly without overflow on ${viewport.name}`, async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });

    await page.setViewportSize({ width: viewport.width, height: viewport.height });

    for (const route of routes) {
      const started = Date.now();
      await page.goto(route.path, { waitUntil: 'domcontentloaded' });
      if ('placeholder' in route) {
        await expect(page.getByPlaceholder(route.placeholder).first()).toBeVisible();
      } else {
        await expect(page.getByText(route.text).first()).toBeVisible();
      }
      expect(Date.now() - started, `${route.path} should become usable within 3 seconds`).toBeLessThan(3000);

      const hasHorizontalOverflow = await page.evaluate(() => {
        const root = document.documentElement;
        const body = document.body;
        const scrollWidth = Math.max(root.scrollWidth, body.scrollWidth);
        const clientWidth = root.clientWidth;
        return scrollWidth > clientWidth + 8;
      });
      expect(hasHorizontalOverflow, `${route.path} should not overflow horizontally on ${viewport.name}`).toBe(false);
    }

    expect(consoleErrors).toEqual([]);
  });
}
