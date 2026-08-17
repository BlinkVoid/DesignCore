// Export an .excalidraw document to SVG, headlessly.
//
// @excalidraw/utils touches browser globals at import time, so every shim
// below must be installed BEFORE the dynamic import -- a static import would
// be hoisted and fail with "window is not defined". See
// docs/plans/2026-08-16-render-backend-findings.md section 3.

import { readFileSync, writeFileSync } from "node:fs";
import { JSDOM } from "jsdom";

const [, , sourcePath, targetPath] = process.argv;
if (!sourcePath || !targetPath) {
  console.error("usage: render.mjs <source.excalidraw> <target.svg>");
  process.exit(2);
}

const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
  url: "https://localhost/",
});
globalThis.window = dom.window;
globalThis.document = dom.window.document;
Object.defineProperty(globalThis, "navigator", {
  value: dom.window.navigator,
  configurable: true,
});
globalThis.devicePixelRatio = 1;
globalThis.location = dom.window.location;
globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);
globalThis.FontFace = class FontFace {};
document.fonts = { add: () => {}, ready: Promise.resolve() };

const { exportToSvg } = await import("@excalidraw/utils");

const scene = JSON.parse(readFileSync(sourcePath, "utf-8"));
const svg = await exportToSvg({
  elements: scene.elements ?? [],
  appState: { exportBackground: true, ...(scene.appState ?? {}) },
  files: scene.files ?? null,
});

writeFileSync(targetPath, svg.outerHTML, "utf-8");
