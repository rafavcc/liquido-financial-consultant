import { afterEach, expect, it, vi } from "vitest";
import { api } from "./client";

afterEach(() => vi.unstubAllGlobals());

it("simulate repassa o signal ao fetch para abortar requisições obsoletas", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  const controller = new AbortController();
  await api.simulate("100", "DATA", "2029-01-01", controller.signal);
  expect(fetchMock.mock.calls[0][1].signal).toBe(controller.signal);
});

it("simulate envia data_alvo só quando horizonte é DATA", async () => {
  const fetchMock = vi.fn().mockImplementation(async () => new Response("{}", { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  await api.simulate("100", "UM_ANO", "2029-01-01");
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ valor: "100", horizonte: "UM_ANO" });
  await api.simulate("100", "DATA", "2029-01-01");
  expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ valor: "100", horizonte: "DATA", data_alvo: "2029-01-01" });
});
