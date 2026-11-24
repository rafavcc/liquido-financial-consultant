import { expect, test } from "@playwright/test";
import { join } from "node:path";

const PRINT = join(process.cwd(), "e2e", "fixtures", "print-sintetico.png");
const DATA_ALVO = "2029-06-15";

test("importa um print, vê o produto no comparador e corrige a falha", async ({ page }) => {
  await page.goto("/importar");
  await page.getByLabel("Escolher prints").setInputFiles(PRINT);
  await expect(page.getByText(/✓ 2 cadastradas/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("⚠ 1 falha")).toBeVisible();

  const nav = page.getByRole("navigation", { name: "Principal" }).filter({ visible: true });
  await nav.getByRole("link", { name: "Comparador" }).click();
  await page.getByLabel("Quanto você quer investir?").fill("50.000,00");
  await page.getByLabel("Preciso do dinheiro em").fill(DATA_ALVO);
  const card = page.locator("article").filter({ hasText: "CDB Alfa 2028" });
  await expect(card).toBeVisible();
  await expect(card.getByText("Importado por IA")).toBeVisible();

  await nav.getByRole("link", { name: "Importar" }).click();
  const falhas = page.getByRole("region", { name: "Falhas" });
  await falhas.getByRole("button", { name: "Corrigir" }).click();
  const dialog = page.getByRole("dialog", { name: "Corrigir oferta" });
  // o formulário só traz o nome quando a interpretação chegou a montar o produto
  await dialog.getByLabel("Nome").fill("CDB Gama 2029");
  await dialog.getByLabel("Nome").fill("CDB Gama 2029");
  await dialog.getByLabel("Vencimento").fill("2029-03-15");
  await dialog.getByRole("button", { name: "Salvar" }).click();
  await expect(dialog).toBeHidden();
  await expect(falhas).toBeHidden();

  await nav.getByRole("link", { name: "Produtos" }).click();
  await expect(page.getByText("CDB Gama 2029")).toBeVisible();
});
