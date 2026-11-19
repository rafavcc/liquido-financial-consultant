import { afterEach, expect, it, vi } from "vitest";
import { api } from "./client";

afterEach(() => vi.unstubAllGlobals());

it("simulate repassa o signal ao fetch para abortar requisições obsoletas", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  const controller = new AbortController();
  await api.simulate("100", "2029-01-01", controller.signal);
  expect(fetchMock.mock.calls[0][1].signal).toBe(controller.signal);
});
