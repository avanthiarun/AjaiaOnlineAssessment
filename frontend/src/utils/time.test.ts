import { describe, expect, it } from "vitest";
import { formatRelative } from "./time";

const NOW = new Date(2026, 10, 18, 15, 0); // Nov 18 2026, 3pm local time

function ago(ms: number): string {
  return new Date(NOW.getTime() - ms).toISOString();
}

describe("formatRelative", () => {
  it.each([
    [30_000, "just now"],
    [5 * 60_000, "5 min ago"],
    [3 * 3_600_000, "3 hr ago"],
    [20 * 3_600_000, "Yesterday"], // 7pm the previous day: under 24h, but not today
  ])("%i ms ago -> %s", (ms, expected) => {
    expect(formatRelative(ago(ms), NOW)).toBe(expected);
  });

  it("shows a short date for older timestamps, with the year only when it differs", () => {
    expect(formatRelative(new Date(2026, 9, 2).toISOString(), NOW)).toMatch(/Oct\s+2|2\s+Oct/);
    expect(formatRelative(new Date(2025, 9, 2).toISOString(), NOW)).toMatch(/2025/);
  });
});
