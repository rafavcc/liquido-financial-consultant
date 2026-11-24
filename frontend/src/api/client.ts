import type { Horizonte, ImportBatchView, ImportCreated, ImportFailureView, ImportItemView, ImportStatus, MarketSummary, ProductData, ProductView, Settings, SimulationResponse } from "./types";

export class ApiError extends Error {
  constructor(public status: number, public messages: string[]) {
    super(messages.join("; ") || `Erro ${status}`);
    this.name = "ApiError";
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      // FormData: o navegador define o Content-Type (multipart + boundary).
      headers: body !== undefined && !(body instanceof FormData) ? { "Content-Type": "application/json" } : undefined,
      body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(0, ["Não foi possível conectar ao servidor."]);
  }
  if (!res.ok) {
    let messages: string[] = [];
    try {
      const data = await res.json();
      const detail = data?.detail;
      messages = Array.isArray(detail) ? detail.map(String) : detail ? [String(detail)] : [];
    } catch {
      /* corpo não-JSON */
    }
    if (messages.length === 0) messages = [`Erro ${res.status} ao falar com o servidor.`];
    throw new ApiError(res.status, messages);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const printUrl = (id: string) => `/api/prints/${id}`;

export const api = {
  simulate: (valor: string, horizonte: Horizonte, dataAlvo: string | null, signal?: AbortSignal) =>
    request<SimulationResponse>(
      "POST",
      "/simulate",
      horizonte === "DATA" ? { valor, horizonte, data_alvo: dataAlvo } : { valor, horizonte },
      signal,
    ),
  market: () => request<MarketSummary>("GET", "/market"),
  refreshMarket: () => request<MarketSummary>("POST", "/market/refresh"),
  products: {
    list: () => request<ProductView[]>("GET", "/products"),
    tesouro: () => request<ProductData[]>("GET", "/products/tesouro"),
    create: (p: Partial<ProductData>) => request<ProductData>("POST", "/products", p),
    update: (id: string, p: Partial<ProductData>) => request<ProductData>("PUT", `/products/${id}`, p),
    remove: (id: string) => request<void>("DELETE", `/products/${id}`),
    duplicate: (id: string) => request<ProductData>("POST", `/products/${id}/duplicate`),
  },
  settings: {
    get: () => request<Settings>("GET", "/settings"),
    update: (s: Settings) => request<Settings>("PUT", "/settings", s),
    reset: () => request<Settings>("POST", "/settings/reset"),
  },
  imports: {
    status: () => request<ImportStatus>("GET", "/imports/status"),
    upload: (files: File[]) => {
      const form = new FormData();
      files.forEach((f) => form.append("arquivos", f));
      return request<ImportCreated>("POST", "/imports", form);
    },
    list: () => request<ImportBatchView[]>("GET", "/imports"),
    get: (id: string) => request<ImportBatchView>("GET", `/imports/${id}`),
    retry: (itemId: string) => request<ImportItemView>("POST", `/imports/items/${itemId}/retry`),
    failures: (status = "ABERTA") => request<ImportFailureView[]>("GET", `/imports/failures?status=${status}`),
    resolve: (id: string, p: Partial<ProductData>) => request<ProductData>("POST", `/imports/failures/${id}/resolve`, p),
    discard: (id: string) => request<void>("POST", `/imports/failures/${id}/discard`),
  },
};
