import { test, expect } from "@playwright/test";

for (const failed of [false, true]) {
  test(`mission updates automatically after background ${failed ? "failure" : "acceptance"}`, async ({
    page,
  }) => {
    let finished = false;
    await page.route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      let json: unknown = { items: [], next_cursor: null };
      if (path.endsWith("/auth/session"))
        json = {
          user: { id: "user_test", display_name: "Test", roles: [] },
          csrf_token: "test",
        };
      else if (path.endsWith("/bookmarks")) json = [];
      else if (path.endsWith("/reports/report_test")) {
        finished = true;
        json = {
          id: "report_test",
          ai_status: failed ? "failed" : "completed",
        };
      } else if (path.endsWith("/missions/progress"))
        json = {
          points: finished && !failed ? 10 : 0,
          items: [
            {
              id: "progress_test",
              mission_id: "mission_test",
              user_id: "user_test",
              report_id: "report_test",
              answer: "",
              status: finished && !failed ? "accepted" : "pending",
              ai_status: finished
                ? failed
                  ? "failed"
                  : "completed"
                : "pending",
              awarded_points: finished && !failed ? 10 : 0,
              review_comment:
                finished && failed
                  ? "Analiza przekroczyła limit czasu. Wyślij zdjęcie ponownie."
                  : null,
              created_at: "2026-10-04T10:00:00Z",
              updated_at: "2026-10-04T10:00:00Z",
            },
          ],
        };
      else if (path.endsWith("/missions/mission_test"))
        json = {
          id: "mission_test",
          target_type: "place",
          place_id: "node/1",
          place_name: "Muzeum testowe",
          title: "Sprawdź: Muzeum testowe",
          attribute: "steps_count",
          fact_id: "node/1:steps_count",
          address: "Kraków",
          location: null,
          points: 10,
          time_minutes: 2,
          available: true,
        };
      await route.fulfill({ json });
    });
    await page.goto("/missions/mission_test");
    await expect(
      page.getByRole("status").filter({ hasText: "Przetwarzanie" }),
    ).toBeVisible();
    await expect(
      page
        .getByRole("status")
        .filter({
          hasText: failed ? "Analiza nie powiodła się" : "Zaakceptowano",
        }),
    ).toBeVisible({ timeout: 10000 });
    if (failed)
      await expect(
        page.getByRole("button", { name: "Wyślij odpowiedź do weryfikacji" }),
      ).toBeVisible();
    else
      await expect(
        page.getByRole("status").filter({ hasText: "10 naliczonych punktów" }),
      ).toBeVisible();
  });
}
