import { expect, test } from "./fixture";

test("confirms and verifies repeated apply and exact restoration", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Pixel 8" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Open phone screen" }),
  ).toBeDisabled();
  const apply = page.getByRole("button", { name: "Apply 0.5×", exact: true });
  const restore = page.getByRole("button", {
    name: "Restore original",
    exact: true,
  });
  await apply.click();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(restore).toBeDisabled();
  for (let attempt = 0; attempt < 2; attempt++) {
    await apply.click();
    await page.getByRole("button", { name: "Confirm" }).click();
    await expect(page.locator("tbody tr td:last-child")).toHaveText([
      "0.5×",
      "0.5×",
      "0.5×",
    ]);
    await expect(page.locator("tbody tr td:first-of-type")).toHaveText([
      "1.0×",
      "1.0×",
      "1.0×",
    ]);
  }
  await restore.click();
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.locator("tbody tr td:last-child")).toHaveText([
    "1.0×",
    "1.0×",
    "1.0×",
  ]);
  await expect(restore).toBeDisabled();
  await expect(
    page.getByText("Restored original profile · 3 values verified"),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("shows an offline device and keeps the profile readable on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: /Test handset/ }).click();
  await expect(
    page.getByText("Reconnect the handset and refresh the device list."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Apply 0.5×" })).toHaveCount(0);
  await page.getByRole("button", { name: /Pixel 8/ }).click();
  await expect(
    page.getByRole("heading", { name: "Animation profile" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
