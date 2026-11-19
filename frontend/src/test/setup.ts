import "@testing-library/jest-dom/vitest";

// jsdom não implementa ResizeObserver (usado pelo ResponsiveContainer do Recharts).
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
