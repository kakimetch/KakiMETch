import { expect, Page, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const trip = {
  trip_id: "trip-1",
  elderly_id: "elderly-1",
  elderly_name: "Mdm Lim Siew Hoon",
  appt_date: "2026-09-08",
  appt_time: "10:00:00",
  destination: "Jurong Community Hospital",
  dialect: "Hokkien",
  weight_kg: 62.5,
  gender_preference: "F",
  wheelchair_required: true,
};

const suggestions = {
  suggestions: [
    {
      escort_id: "escort-1",
      name: "Mei Ling",
      gender: "F",
      score: 3,
      flairs: ["Speaks Hokkien", "Wheelchair capable", "Gender preference met"],
    },
    {
      escort_id: "escort-2",
      name: "Siti Aishah",
      gender: "F",
      score: 1,
      flairs: ["Wheelchair capable"],
    },
  ],
  warning: null,
};

async function mockStandardApi(page: Page) {
  await page.route("**/matching-queue", (route) =>
    route.fulfill({ json: [trip] }),
  );
  await page.route("**/schedule", (route) =>
    route.fulfill({
      json: [
        {
          trip_id: "trip-scheduled",
          elderly_name: "Mr Tan Ah Kow",
          escort_name: "Siti Aishah",
          appt_date: "2026-09-09",
          appt_time: "13:30:00",
          destination: "Ng Teng Fong General Hospital",
        },
      ],
    }),
  );
  await page.route("**/trips/trip-1/escort-suggestions?limit=3", (route) =>
    route.fulfill({ json: suggestions }),
  );
  await page.route(
    "**/elderly-clients/elderly-1/matching-profile",
    async (route) => {
      const body = route.request().postDataJSON();
      await route.fulfill({ json: { elderly_id: "elderly-1", ...body } });
    },
  );
  await page.route("**/trips/trip-1/confirm-escort", (route) => {
    const body = route.request().postDataJSON();
    return route.fulfill({
      json: {
        trip_id: "trip-1",
        escort_id: body.escort_id,
        status: "scheduled",
        assignment_override: body.assignment_override,
      },
    });
  });
}

test("confirms a suggested escort and removes the patient module", async ({
  page,
}) => {
  await mockStandardApi(page);
  await page.goto("/app/matching");
  await expect(page.getByRole("button", { name: /Mdm Lim Siew Hoon/ })).toBeVisible();
  await page.getByRole("button", { name: /Mdm Lim Siew Hoon/ }).click();
  await expect(
    page.getByRole("dialog", { name: "Mdm Lim Siew Hoon" }),
  ).toBeVisible();
  await page.getByRole("radio", { name: /Mei Ling/ }).check();
  await page.getByRole("button", { name: "Confirm Mei Ling" }).click();
  await expect(page.getByText("Mei Ling is assigned")).toBeVisible();
  await page.getByRole("button", { name: "Match next appointment" }).click();
  await expect(
    page.getByRole("button", { name: /Mdm Lim Siew Hoon/ }),
  ).toHaveCount(0);
});

test("edits matching details before confirming", async ({ page }) => {
  await mockStandardApi(page);
  await page.goto("/app/matching");
  await page.getByRole("button", { name: /Mdm Lim Siew Hoon/ }).click();
  await page.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Dialect").fill("Cantonese");
  const patchRequest = page.waitForRequest(
    "**/elderly-clients/elderly-1/matching-profile",
  );
  await page.getByRole("button", { name: "Save and refresh" }).click();
  expect((await patchRequest).postDataJSON().dialect).toBe("Cantonese");
  await expect(
    page.getByText("Details saved. Suggestions have been refreshed."),
  ).toBeVisible();
});

test("reviews existing patient and escort matches in a separate tab", async ({
  page,
}) => {
  await mockStandardApi(page);
  await page.goto("/app/matching");
  await page.getByRole("tab", { name: /Existing matches/ }).click();
  await expect(
    page.getByRole("heading", { name: "Existing patient–escort matches" }),
  ).toBeVisible();
  await expect(page.getByText("Mr Tan Ah Kow")).toBeVisible();
  await expect(page.getByText("Siti Aishah")).toBeVisible();
});

test("requires a reason for a manual override", async ({ page }) => {
  await page.route("**/matching-queue", (route) =>
    route.fulfill({ json: [trip] }),
  );
  await page.route("**/trips/trip-1/escort-suggestions?limit=3", (route) =>
    route.fulfill({
      json: { suggestions: [], warning: "No viable escort is available." },
    }),
  );
  await page.route("**/trips/trip-1/escort-options", (route) =>
    route.fulfill({
      json: [
        {
          escort_id: "escort-2",
          name: "Siti Aishah",
          gender: "F",
          dialects: ["Malay"],
          available_days: ["Mon"],
          available_timeslot: "9am–1pm",
          wheelchair_handling_capable: true,
          issues: ["Escort is unavailable at this appointment time."],
        },
      ],
    }),
  );
  await page.route("**/trips/trip-1/confirm-escort", (route) =>
    route.fulfill({
      json: {
        trip_id: "trip-1",
        escort_id: "escort-2",
        status: "scheduled",
        assignment_override: true,
      },
    }),
  );

  await page.goto("/app/matching");
  await page.getByRole("button", { name: /Mdm Lim Siew Hoon/ }).click();
  await expect(page.getByText("Manual review needed")).toBeVisible();
  await page.getByRole("radio", { name: /Siti Aishah/ }).check();
  const confirm = page.getByRole("button", {
    name: "Confirm Siti Aishah with override",
  });
  await expect(confirm).toBeDisabled();
  await page
    .getByLabel("Reason for overriding")
    .fill("Escort confirmed availability by phone.");
  await expect(confirm).toBeEnabled();
});

test("retries when the patient queue fails", async ({ page }) => {
  const queuePattern = "**/matching-queue";
  const unavailable = (route: Parameters<Parameters<Page["route"]>[1]>[0]) =>
    route.fulfill({
      status: 503,
      json: { detail: "Matching service is temporarily unavailable." },
    });
  await page.route(queuePattern, unavailable);
  await page.goto("/app/matching");
  await expect(page.getByText("Patients could not load")).toBeVisible();
  await page.unroute(queuePattern, unavailable);
  await page.route(queuePattern, (route) => route.fulfill({ json: [trip] }));
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByRole("button", { name: /Mdm Lim Siew Hoon/ }),
  ).toBeVisible();
});

test("can complete the standard flow using only the keyboard", async ({
  page,
}) => {
  await mockStandardApi(page);
  await page.goto("/app/matching");
  await page.getByRole("button", { name: /Mdm Lim Siew Hoon/ }).focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("button", { name: "All patients" }),
  ).toBeFocused();
  await page.getByRole("radio", { name: /Mei Ling/ }).focus();
  await page.keyboard.press("Space");
  await page.getByRole("button", { name: "Confirm Mei Ling" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByText("Mei Ling is assigned")).toBeVisible();
});

test("captures the patient modules and focused drawer at review widths", async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== "desktop",
    "One browser captures all review widths.",
  );
  await mockStandardApi(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/app/matching");
  await expect(page.getByRole("button", { name: /Mdm Lim Siew Hoon/ })).toBeVisible();
  await page.screenshot({ path: "output/playwright/screenshots/patient-modules-desktop.png", fullPage: true });

  await page.getByRole("button", { name: /Mdm Lim Siew Hoon/ }).click();
  await expect(page.getByText("Speaks Hokkien")).toBeVisible();
  await page.screenshot({
    path: "output/playwright/screenshots/matching-drawer-desktop.png",
    fullPage: true,
  });

  await page.setViewportSize({ width: 1024, height: 768 });
  await page.screenshot({
    path: "output/playwright/screenshots/matching-drawer-compact.png",
    fullPage: true,
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "output/playwright/screenshots/matching-drawer-mobile.png",
    fullPage: true,
  });
});

test("has no automatically detectable WCAG 2.2 A or AA violations", async ({
  page,
}) => {
  await mockStandardApi(page);
  await page.goto("/app/matching");
  await expect(page.getByRole("button", { name: /Mdm Lim Siew Hoon/ })).toBeVisible();
  const overview = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  expect(overview.violations).toEqual([]);

  await page.getByRole("button", { name: /Mdm Lim Siew Hoon/ }).click();
  await expect(page.getByText("Speaks Hokkien")).toBeVisible();
  const drawer = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(drawer.violations).toEqual([]);
});
