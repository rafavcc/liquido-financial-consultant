// Gera os PNGs dos ícones a partir de public/icons/icon.svg usando o Chromium do Playwright.
// Uso: node scripts/generate-icons.mjs
import { chromium } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const dir = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "icons");
const svg = readFileSync(join(dir, "icon.svg"), "utf8");
const targets = [
  ["icon-192.png", 192, false],
  ["icon-512.png", 512, false],
  // iOS aplica o próprio arredondamento: o ícone da tela de início é um quadrado cheio
  ["apple-touch-icon.png", 180, true],
];

const browser = await chromium.launch();
for (const [name, size, square] of targets) {
  const markup = square ? svg.replace('rx="112"', 'rx="0"') : svg;
  const page = await browser.newPage({ viewport: { width: size, height: size } });
  await page.setContent(
    `<style>html,body{margin:0;background:transparent}svg{display:block;width:${size}px;height:${size}px}</style>${markup}`,
  );
  writeFileSync(join(dir, name), await page.screenshot({ omitBackground: true }));
  await page.close();
}
await browser.close();
