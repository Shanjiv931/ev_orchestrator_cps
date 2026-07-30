import { describe, expect, it } from "vitest";
import { isStaleVerification, safetyBadgeClasses, safetyColor, STALE_VERIFICATION_THRESHOLD_HOURS } from "./format";

describe("safetyColor", () => {
  it("returns green for high safety scores", () => {
    expect(safetyColor(0.9)).toBe("#16a34a");
    expect(safetyColor(0.7)).toBe("#16a34a");
  });

  it("returns amber for medium safety scores", () => {
    expect(safetyColor(0.5)).toBe("#f59e0b");
  });

  it("returns red for low safety scores", () => {
    expect(safetyColor(0.1)).toBe("#dc2626");
  });
});

describe("safetyBadgeClasses", () => {
  it("always pairs a background with an explicit text color, for both themes", () => {
    for (const score of [0.9, 0.5, 0.1]) {
      const classes = safetyBadgeClasses(score);
      expect(classes).toMatch(/\btext-\w+-\d00\b/);
      expect(classes).toMatch(/\bdark:text-\w+-\d00\b/);
      expect(classes).toMatch(/\bbg-\w+-100\b/);
      expect(classes).toMatch(/\bdark:bg-\w+-900\b/);
    }
  });
});

describe("isStaleVerification", () => {
  it("is false right at the threshold", () => {
    expect(isStaleVerification(STALE_VERIFICATION_THRESHOLD_HOURS)).toBe(false);
  });

  it("is true just past the threshold", () => {
    expect(isStaleVerification(STALE_VERIFICATION_THRESHOLD_HOURS + 0.01)).toBe(true);
  });

  it("is false for a fresh verification", () => {
    expect(isStaleVerification(0)).toBe(false);
  });
});
