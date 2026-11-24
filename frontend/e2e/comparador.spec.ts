import { expect, test } from "@playwright/test";

const DATA_ALVO = "2029-06-15";

test("compara produtos, abre o detalhe e salva configurações", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Quanto você quer investir?").fill("50.000,00");
  await page.getByLabel("Preciso do dinheiro em").fill(DATA_ALVO);

  const verde = page.locator("section").filter({ has: page.getByRole("heading", { name: /Vencem até a sua data/ }) });
  await expect(verde).toBeVisible();
  const cards = verde.locator("article");
  await expect(cards.first()).toBeVisible();
  expect(await cards.count()).toBeGreaterThanOrEqual(3);
  await expect(cards.first().getByText("#1")).toBeVisible();

  await cards.first().getByRole("button").first().click();
  const detalhe = page.getByRole("dialog");
  await expect(detalhe.getByText("Valor líquido")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(detalhe).toBeHidden();

  await page.getByRole("navigation", { name: "Principal" }).filter({ visible: true }).getByRole("link", { name: "Configurações" }).click();
  await expect(page.getByRole("heading", { name: "Configurações" })).toBeVisible();
  await page.getByLabel("Custódia B3 (% ao ano)").fill("0,25");
  await page.getByRole("button", { name: "Salvar alterações" }).click();
  await expect(page.getByRole("button", { name: "Salvar alterações" })).toBeHidden();
  await expect(page.getByRole("alert")).toHaveCount(0);

  await page.getByRole("navigation", { name: "Principal" }).filter({ visible: true }).getByRole("link", { name: "Comparador" }).click();
  await expect(page.getByLabel("Quanto você quer investir?")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("rota do app e API inexistente", async ({ page, request }) => {
  await page.goto("/produtos");
  await expect(page.getByRole("heading", { name: "Produtos", exact: true })).toBeVisible();
  const r = await request.get("/api/nao-existe");
  expect(r.status()).toBe(404);
});

test("sem data e custo-benefício", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Quanto você quer investir?").fill("50.000,00");
  await page.getByRole("radio", { name: "Sem data" }).click();
  await expect(page.getByLabel("Preciso do dinheiro em")).toHaveCount(0);
  const secao = page.locator("section").filter({ has: page.getByRole("heading", { name: /Todos os produtos/ }) });
  await expect(secao.locator("article").first()).toBeVisible();
  await expect(secao.locator("article").first().getByText(/a\.a\./).first()).toBeVisible();
  await page.getByLabel("Ordenar por").selectOption("CUSTO_BENEFICIO");
  await expect(secao.locator("article").first()).toBeVisible();
  await page.getByRole("radio", { name: "2 anos" }).click();
  await expect(page.getByText(/Resgate em \d{2}\/\d{2}\/\d{4}/)).toBeVisible();
});
