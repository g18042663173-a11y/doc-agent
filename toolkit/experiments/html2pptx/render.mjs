import fs from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
import process from "node:process";

import { chromium } from "playwright";
import pptxgen from "pptxgenjs";

const WIDTH_PX = 1280;
const HEIGHT_PX = 720;
const WIDTH_IN = 13.34;
const HEIGHT_IN = 7.5;
const SUPPORTED_LAYOUTS = new Set(["cover", "title_bullets", "two_column", "cards", "table", "chart"]);

function argument(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) throw new Error(`missing ${name}`);
  return process.argv[index + 1];
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>\"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character]);
}

function themeColor(theme, name, fallback) {
  return String(theme?.colors?.[name] ?? fallback).replace(/^#/, "").toUpperCase();
}

function cssColor(theme, name, fallback) {
  return `#${themeColor(theme, name, fallback)}`;
}

function cjkFont(theme) {
  return theme?.fonts?.east_asia?.[0] ?? "微软雅黑";
}

function sha256(value) {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function textBlock(text, style) {
  const css = Object.entries(style).map(([key, value]) => `${key}:${value}`).join(";");
  return `<div data-pptx="text" style="${css}">${escapeHtml(text)}</div>`;
}

function shapeBlock(style, { decoration = false } = {}) {
  const css = Object.entries(style).map(([key, value]) => `${key}:${value}`).join(";");
  return `<div data-pptx="shape"${decoration ? " data-pptx-decoration=\"true\"" : ""} style="${css}"></div>`;
}

function titleBlock(slide, theme) {
  return textBlock(slide.title ?? "", {
    position: "absolute", left: "55px", top: "30px", width: "1170px", height: "62px",
    color: cssColor(theme, "title", "1D1D1A"), "font-family": `${cjkFont(theme)}, Arial, sans-serif`,
    "font-size": "30px", "font-weight": "700", "line-height": "1.25", overflow: "hidden",
  });
}

function bulletRows(items, theme, { left = 75, top = 150, width = 1120 } = {}) {
  return (items ?? []).map((item, index) => textBlock(`• ${item.text ?? item}`, {
    position: "absolute", left: `${left}px`, top: `${top + index * 64}px`, width: `${width}px`, height: "50px",
    color: cssColor(theme, "body", "1D1D1A"), "font-family": `${cjkFont(theme)}, Arial, sans-serif`,
    "font-size": "20px", "line-height": "1.35", overflow: "hidden",
  })).join("\n");
}

function buildHtml(slide, theme) {
  let content = "";
  if (slide.layout === "cover") {
    content += shapeBlock({ position: "absolute", left: "58px", top: "560px", width: "150px", height: "12px", background: cssColor(theme, "hw_red", "C7000B") });
    content += textBlock(slide.title, {
      position: "absolute", left: "55px", top: "175px", width: "1160px", height: "120px",
      color: cssColor(theme, "title", "1D1D1A"), "font-family": `${cjkFont(theme)}, Arial, sans-serif`,
      "font-size": "46px", "font-weight": "700", "line-height": "1.2", overflow: "hidden",
    });
    content += textBlock(slide.subtitle ?? "", {
      position: "absolute", left: "155px", top: "330px", width: "900px", height: "52px",
      color: cssColor(theme, "secondary", "666666"), "font-family": `${cjkFont(theme)}, Arial, sans-serif`,
      "font-size": "22px", "line-height": "1.3", overflow: "hidden",
    });
  } else if (slide.layout === "title_bullets") {
    content += titleBlock(slide, theme);
    content += bulletRows(slide.bullets, theme);
  } else if (slide.layout === "two_column") {
    content += titleBlock(slide, theme);
    const columns = [[slide.left, 75], [slide.right, 650]];
    for (const [column, left] of columns) {
      content += shapeBlock({ position: "absolute", left: `${left}px`, top: "135px", width: "530px", height: "410px", background: cssColor(theme, "table_stripe", "F5F5F5"), border: `1px solid ${cssColor(theme, "border", "DDDDDD")}` });
      content += textBlock(column?.heading ?? "", {
        position: "absolute", left: `${left + 24}px`, top: "165px", width: "480px", height: "48px", color: cssColor(theme, "hw_red", "C7000B"),
        "font-family": `${cjkFont(theme)}, Arial, sans-serif`, "font-size": "22px", "font-weight": "700", overflow: "hidden",
      });
      const values = [column?.text, ...(column?.bullets ?? []).map((item) => `• ${item.text ?? item}`)].filter(Boolean);
      content += values.map((value, index) => textBlock(value, {
        position: "absolute", left: `${left + 24}px`, top: `${235 + index * 58}px`, width: "480px", height: "48px", color: cssColor(theme, "body", "1D1D1A"),
        "font-family": `${cjkFont(theme)}, Arial, sans-serif`, "font-size": "18px", "line-height": "1.3", overflow: "hidden",
      })).join("\n");
    }
  } else if (slide.layout === "cards") {
    content += titleBlock(slide, theme);
    const cards = slide.cards ?? [];
    const cardWidth = Math.floor((1130 - Math.max(cards.length - 1, 0) * 24) / Math.max(cards.length, 1));
    cards.forEach((card, index) => {
      const left = 75 + index * (cardWidth + 24);
      content += shapeBlock({ position: "absolute", left: `${left}px`, top: "175px", width: `${cardWidth}px`, height: "260px", background: cssColor(theme, "table_stripe", "F5F5F5"), border: `1px solid ${cssColor(theme, "border", "DDDDDD")}` });
      content += shapeBlock(
        { position: "absolute", left: `${left}px`, top: "175px", width: `${cardWidth}px`, height: "7px", background: cssColor(theme, "hw_red", "C7000B") },
        { decoration: true },
      );
      content += textBlock(card.title, { position: "absolute", left: `${left + 22}px`, top: "215px", width: `${cardWidth - 44}px`, height: "42px", color: cssColor(theme, "title", "1D1D1A"), "font-family": `${cjkFont(theme)}, Arial, sans-serif`, "font-size": "21px", "font-weight": "700", overflow: "hidden" });
      content += textBlock(card.desc, { position: "absolute", left: `${left + 22}px`, top: "280px", width: `${cardWidth - 44}px`, height: "100px", color: cssColor(theme, "body", "1D1D1A"), "font-family": `${cjkFont(theme)}, Arial, sans-serif`, "font-size": "17px", "line-height": "1.35", overflow: "hidden" });
    });
  } else if (slide.layout === "table") {
    content += titleBlock(slide, theme);
    const rows = [slide.table?.header ?? [], ...(slide.table?.rows ?? [])];
    const cells = rows.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("");
    content += `<table data-pptx="table" style="position:absolute;left:80px;top:150px;width:1110px;border-collapse:collapse;font-family:${cjkFont(theme)},Arial,sans-serif;font-size:17px;color:${cssColor(theme, "body", "1D1D1A")}">${cells}</table>`;
  } else if (slide.layout === "chart") {
    content += titleBlock(slide, theme);
    content += `<div data-pptx="chart" style="position:absolute;left:120px;top:150px;width:820px;height:410px;border:1px solid ${cssColor(theme, "border", "DDDDDD")};font-family:Arial,sans-serif">${escapeHtml(slide.chart?.kind ?? "chart")}</div>`;
  } else {
    throw new Error(`unsupported HTML experiment layout: ${slide.layout}`);
  }
  return `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;width:${WIDTH_PX}px;height:${HEIGHT_PX}px;overflow:hidden;background:${cssColor(theme, "background", "FFFFFF")}}*{box-sizing:border-box}td{border:1px solid ${cssColor(theme, "border", "DDDDDD")};padding:10px}tr:first-child{background:${cssColor(theme, "hw_red", "C7000B")};color:#FFFFFF;font-weight:700}</style></head><body>${content}</body></html>`;
}

function rgbToHex(value) {
  const values = String(value).match(/\d+/g);
  if (!values || values.length < 3) return "1D1D1A";
  return values.slice(0, 3).map((item) => Number(item).toString(16).padStart(2, "0")).join("").toUpperCase();
}

function pptBox(rect) {
  return { x: rect.x * WIDTH_IN / WIDTH_PX, y: rect.y * HEIGHT_IN / HEIGHT_PX, w: rect.width * WIDTH_IN / WIDTH_PX, h: rect.height * HEIGHT_IN / HEIGHT_PX };
}

async function htmlToSlide(browser, pptx, html, model, theme, classification, currentSlide, totalSlides) {
  const page = await browser.newPage({ viewport: { width: WIDTH_PX, height: HEIGHT_PX } });
  await page.setContent(html, { waitUntil: "load" });
  const inspected = await page.evaluate(() => {
    const body = document.body;
    const overflow = body.scrollWidth > body.clientWidth || body.scrollHeight > body.clientHeight;
    const gradients = [...document.querySelectorAll("*")].some((element) => getComputedStyle(element).backgroundImage.includes("gradient"));
    const elements = [...document.querySelectorAll("[data-pptx]")].map((element) => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return { kind: element.dataset.pptx, decoration: element.dataset.pptxDecoration === "true", text: element.innerText, rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }, style: { color: style.color, backgroundColor: style.backgroundColor, fontFamily: style.fontFamily, fontSize: style.fontSize, fontWeight: style.fontWeight, lineHeight: style.lineHeight } };
    });
    return { overflow, gradients, elements };
  });
  const errors = [];
  if (inspected.overflow) errors.push("html_body_overflow");
  if (inspected.gradients) errors.push("unsupported_css_gradient");
  if (errors.length) {
    await page.close();
    return {
      errors,
      html_validation: {
        body_overflow: inspected.overflow,
        unsupported_css_gradient: inspected.gradients,
        element_count: inspected.elements.length,
      },
    };
  }
  const slide = pptx.addSlide();
  for (const element of inspected.elements.filter((item) => item.kind === "shape")) {
    const box = pptBox(element.rect);
    slide.addShape(pptx.ShapeType.rect, {
      ...box,
      fill: { color: rgbToHex(element.style.backgroundColor) },
      line: { color: themeColor(theme, "border", "DDDDDD"), pt: 0.5 },
      objectName: element.decoration ? "HW_DECORATION:HTML_CARD_ACCENT" : undefined,
    });
  }
  for (const element of inspected.elements.filter((item) => item.kind === "text")) {
    const box = pptBox(element.rect);
    const fontSize = Math.max(8, Number.parseFloat(element.style.fontSize) * 72 / 96);
    slide.addText(element.text, { ...box, margin: 0, breakLine: false, fontFace: cjkFont(theme), fontSize, color: rgbToHex(element.style.color), bold: Number(element.style.fontWeight) >= 600, valign: "mid" });
  }
  const tableElement = inspected.elements.find((item) => item.kind === "table");
  if (tableElement && model.table) addNativeTable(slide, pptx, pptBox(tableElement.rect), model.table, theme);
  const chartElement = inspected.elements.find((item) => item.kind === "chart");
  if (chartElement && model.chart) addNativeChart(slide, pptx, pptBox(chartElement.rect), model.chart, theme);
  addFooter(slide, classification, currentSlide, totalSlides, theme);
  await page.close();
  return {
    errors: [],
    html_validation: {
      body_overflow: inspected.overflow,
      unsupported_css_gradient: inspected.gradients,
      element_count: inspected.elements.length,
    },
  };
}

function addNativeTable(slide, pptx, box, table, theme) {
  const rows = [table.header, ...table.rows];
  slide.addTable(rows, { ...box, border: { pt: 0.5, color: themeColor(theme, "border", "DDDDDD") }, color: themeColor(theme, "body", "1D1D1A"), fontFace: cjkFont(theme), fontSize: 10, fill: themeColor(theme, "background", "FFFFFF"), autoFit: false, margin: 0.06 });
}

function addFooter(slide, classification, currentSlide, totalSlides, theme) {
  slide.addText(classification, { x: 0.57, y: 7.0, w: 4.3, h: 0.22, margin: 0, fontFace: cjkFont(theme), fontSize: 9, color: themeColor(theme, "secondary", "666666") });
  slide.addText(`${currentSlide}/${totalSlides}`, { x: 12.2, y: 7.0, w: 0.6, h: 0.22, margin: 0, fontFace: cjkFont(theme), fontSize: 9, color: themeColor(theme, "secondary", "666666"), align: "right" });
}

function addNativeChart(slide, pptx, box, chart, theme) {
  const type = { bar: pptx.ChartType.bar, line: pptx.ChartType.line, pie: pptx.ChartType.pie }[chart.kind];
  if (!type) throw new Error(`unsupported chart kind: ${chart.kind}`);
  const data = chart.series.map((series) => ({ name: series.name, labels: chart.categories, values: series.values }));
  slide.addChart(type, data, {
    ...box,
    showLegend: chart.legend_position !== "none" && chart.series.length > 1,
    legendPos: chart.legend_position === "top" ? "t" : "r",
    showValue: Boolean(chart.show_data_labels),
    showPercent: chart.kind === "pie",
    chartColors: [themeColor(theme, "accent1", "C7000B"), themeColor(theme, "accent6", "30B5C5"), themeColor(theme, "accent5", "61B230")],
    catAxisLabelRotate: chart.categories.some((item) => String(item).length > 8) ? 45 : 0,
    showTitle: false,
  });
}

async function main() {
  const inputPath = path.resolve(argument("--input"));
  const outputPath = path.resolve(argument("--output"));
  const reportPath = path.resolve(argument("--report"));
  const themePath = path.resolve(argument("--theme"));
  const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
  const theme = JSON.parse(await fs.readFile(themePath, "utf8"));
  const deck = payload.deck ?? payload;
  const unsupported = deck.slides.filter((slide) => !SUPPORTED_LAYOUTS.has(slide.layout)).map((slide) => slide.layout);
  if (unsupported.length) throw new Error(`unsupported layouts: ${unsupported.join(", ")}`);
  const htmlDir = path.join(path.dirname(outputPath), "html");
  await fs.mkdir(htmlDir, { recursive: true });
  const pptx = new pptxgen();
  pptx.defineLayout({ name: "HUAWEI_WIDE", width: WIDTH_IN, height: HEIGHT_IN });
  pptx.layout = "HUAWEI_WIDE";
  pptx.author = "DeckIR HTML/PptxGenJS Experiment";
  pptx.subject = "Non-production engine benchmark";
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const slideReports = [];
  try {
    for (const [index, slide] of deck.slides.entries()) {
      const html = buildHtml(slide, theme);
      const htmlPath = path.join(htmlDir, `slide-${String(index + 1).padStart(3, "0")}.html`);
      await fs.writeFile(htmlPath, html, "utf8");
      const result = await htmlToSlide(browser, pptx, html, slide, theme, deck.meta.classification, index + 1, deck.slides.length);
      slideReports.push({
        index: index + 1,
        layout: slide.layout,
        html: path.basename(htmlPath),
        html_sha256: sha256(html),
        errors: result.errors,
        html_validation: result.html_validation,
      });
    }
  } finally {
    await browser.close();
  }
  const errors = slideReports.flatMap((slide) => slide.errors.map((error) => `slide-${slide.index}:${error}`));
  if (errors.length) throw new Error(errors.join(", "));
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await pptx.writeFile({ fileName: outputPath });
  await fs.writeFile(reportPath, JSON.stringify({ html2pptx_experiment_version: "1.0", pass: true, slides: slideReports, html_directory: htmlDir, node: process.version }, null, 2) + "\n", "utf8");
}

main().catch((error) => { console.error(error.stack || error.message); process.exitCode = 1; });
