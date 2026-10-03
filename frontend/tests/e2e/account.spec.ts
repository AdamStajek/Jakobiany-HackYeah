import { test, expect } from "@playwright/test";

test("konto, profil, zdjęcie, zgłoszenie i zweryfikowana misja pozostają po ponownym logowaniu", async ({
  page,
  browser,
  baseURL,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const email = `user-${test.info().project.name}-${Date.now()}@example.com`;
  const password = "browser-user-password";
  await page.goto("/register");
  await page.getByLabel("Imię", { exact: true }).fill("Anna");
  await page.getByLabel("E-mail", { exact: true }).fill(email);
  await page.getByLabel("Hasło", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Utwórz konto", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Cześć, Anna!" }),
  ).toBeVisible();

  await page.getByRole("link", { name: "Edytuj profil potrzeb" }).click();
  await page
    .getByLabel("Opisz swoje potrzeby")
    .fill("Bez schodów, odpoczynek co 300 metrów.");
  await page.getByRole("button", { name: "Dalej", exact: true }).click();
  await expect(page.getByLabel("Maksymalna liczba stopni")).toHaveValue("0");
  await expect(page.getByLabel("Odpoczynek co najwyżej co (m)")).toHaveValue(
    "300",
  );
  await page
    .getByRole("button", { name: "Zapisz profil", exact: true })
    .click();
  await expect(
    page.getByText("Profil zapisano na Twoim koncie.", { exact: false }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Opisz swoje potrzeby")).toHaveValue(
    "Bez schodów, odpoczynek co 300 metrów.",
  );
  await page.getByRole("button", { name: "Wybierz potrzeby ręcznie" }).click();
  await expect(page.getByLabel("Maksymalna liczba stopni")).toHaveValue("0");
  await page.getByLabel("Maksymalna wysokość progu (cm)").fill("2");
  await page
    .getByRole("button", { name: "Zapisz profil", exact: true })
    .click();
  await expect(
    page.getByText("Profil zapisano na Twoim koncie.", { exact: false }),
  ).toBeVisible();

  await page.goto("/place/node%2F1");
  await expect(
    page.getByRole("heading", { name: "Muzeum integracyjne", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Zapisz", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Zapisano", exact: true }),
  ).toBeVisible();
  await page.goto("/profile");
  await expect(
    page.getByRole("link", { name: "Muzeum integracyjne" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("link", { name: "Muzeum integracyjne" }),
  ).toBeVisible();

  await page.goto("/report/problem?place=node%2F1");
  await page
    .getByLabel("Opisz problem", { exact: true })
    .fill("Podjazd jest zamknięty z powodu remontu.");
  await page
    .getByLabel("Zdjęcie (opcjonalnie)", { exact: true })
    .setInputFiles("tests/fixtures/evidence.png");
  await page
    .getByRole("button", { name: "Wyślij zgłoszenie", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Dziękujemy za pomoc!" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Moje zgłoszenia", exact: true })
    .click();
  await expect(
    page.getByText("Podjazd jest zamknięty z powodu remontu."),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: "Zdjęcie dołączone do zgłoszenia" }),
  ).toBeVisible();
  await expect
    .poll(() =>
      page
        .getByRole("img", { name: "Zdjęcie dołączone do zgłoszenia" })
        .evaluate((node) => (node as HTMLImageElement).naturalWidth),
    )
    .toBe(8);

  await page.goto("/missions");
  const card = page.locator(".mission-card").first();
  const missionTitle = await card.getByRole("heading").innerText();
  await card.click();
  await page
    .getByRole("button", { name: "Rozpocznij misję", exact: true })
    .click();
  await page
    .getByLabel("Co udało Ci się sprawdzić?")
    .fill("Wejście sprawdzono w terenie: nie ma stopni.");
  await page
    .getByRole("button", {
      name: "Wyślij odpowiedź do weryfikacji",
      exact: true,
    })
    .click();
  await expect(
    page.getByText("Oczekuje na weryfikację · 0 naliczonych punktów"),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Oczekuje na weryfikację · 0 naliczonych punktów"),
  ).toBeVisible();

  const moderator = await browser.newContext({ baseURL });
  const reviewPage = await moderator.newPage();
  try {
    await reviewPage.goto("/login");
    await reviewPage
      .getByLabel("E-mail", { exact: true })
      .fill("moderator@example.com");
    await reviewPage
      .getByLabel("Hasło", { exact: true })
      .fill("moderator-test-password");
    await reviewPage
      .getByRole("button", { name: "Zaloguj się", exact: true })
      .click();
    await reviewPage
      .getByRole("link", { name: "Weryfikuj zgłoszenia i misje" })
      .click();
    const missionReview = reviewPage.locator(".review-card").filter({
      has: reviewPage.getByRole("heading", {
        name: missionTitle,
        exact: true,
      }),
    });
    await missionReview
      .getByLabel("Komentarz moderatora")
      .fill("Sprawdzono opis i potwierdzono wykonanie zadania.");
    await missionReview
      .getByRole("button", { name: "Zaakceptuj", exact: true })
      .click();
    await expect(missionReview).toHaveCount(0);
  } finally {
    await moderator.close();
  }

  await page
    .getByRole("button", { name: "Odśwież status", exact: true })
    .click();
  await expect(
    page.getByText("Zaakceptowano · 30 naliczonych punktów"),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Zaakceptowano · 30 naliczonych punktów"),
  ).toBeVisible();
  await page.goto("/profile");
  await expect(page.locator(".points")).toHaveText("30 pkt");
  await page.getByRole("button", { name: "Wyloguj się", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Twój profil", exact: true }),
  ).toBeVisible();
  await page
    .locator(".profile-grid")
    .getByRole("link", { name: "Zaloguj się", exact: true })
    .click();
  await page.getByLabel("E-mail", { exact: true }).fill(email);
  await page.getByLabel("Hasło", { exact: true }).fill("incorrect-password");
  await page.getByRole("button", { name: "Zaloguj się", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "Nieprawidłowy e-mail lub hasło.",
  );
  await page.getByLabel("Hasło", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Zaloguj się", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Cześć, Anna!" }),
  ).toBeVisible();
  await expect(page.locator(".points")).toHaveText("30 pkt");
  await expect(
    page.getByRole("link", { name: "Muzeum integracyjne" }),
  ).toBeVisible();
  await expect(
    page.getByText("Podjazd jest zamknięty z powodu remontu."),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
