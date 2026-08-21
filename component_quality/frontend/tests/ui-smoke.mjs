import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const outputDir = path.resolve("test-artifacts");
await fs.mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: true,
});

try {
  const desktop = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await desktop.goto("http://127.0.0.1:5173", { waitUntil: "networkidle" });
  await desktop.getByRole("heading", { name: "AI Research Mentor" }).waitFor();
  await desktop.screenshot({
    path: path.join(outputDir, "dashboard-desktop.png"),
    fullPage: true,
  });

  await desktop.getByRole("button", { name: "Weak Methodology" }).click();
  await desktop.getByRole("button", { name: "Analyze text" }).click();
  await desktop.getByRole("heading", { name: "Your next improvement step" }).waitFor({
    timeout: 30000,
  });

  const feedbackCount = await desktop.locator(".feedback-card").count();
  const resourceCount = await desktop.locator(".resource-card").count();
  const desktopOverflow = await desktop.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  if (feedbackCount !== 3 || resourceCount !== 3 || desktopOverflow) {
    throw new Error(
      `Desktop verification failed: feedback=${feedbackCount}, resources=${resourceCount}, overflow=${desktopOverflow}`,
    );
  }

  await desktop.screenshot({
    path: path.join(outputDir, "analysis-results-desktop.png"),
    fullPage: true,
  });

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mobile.goto("http://127.0.0.1:5173", { waitUntil: "networkidle" });
  await mobile.getByRole("heading", { name: "AI Research Mentor" }).waitFor();
  const mobileOverflow = await mobile.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  if (mobileOverflow) {
    throw new Error("Mobile layout has horizontal overflow.");
  }

  await mobile.screenshot({
    path: path.join(outputDir, "dashboard-mobile.png"),
    fullPage: true,
  });

  await mobile.getByRole("button", { name: "Missing Citation" }).click();
  await mobile.getByRole("button", { name: "Analyze text" }).click();
  await mobile.getByRole("heading", { name: "Your next improvement step" }).waitFor({
    timeout: 30000,
  });
  const mobileResultOverflow = await mobile.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  if (mobileResultOverflow) {
    throw new Error("Mobile result layout has horizontal overflow.");
  }
  await mobile.screenshot({
    path: path.join(outputDir, "analysis-results-mobile.png"),
    fullPage: true,
  });

  console.log(
    JSON.stringify(
      {
        feedbackCount,
        resourceCount,
        desktopOverflow,
        mobileOverflow,
        mobileResultOverflow,
      },
      null,
      2,
    ),
  );
} finally {
  await browser.close();
}
