import { describe, expect, it } from "vitest";
import { resources } from "./i18n";

function flattenKeys(obj: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === "object" && !Array.isArray(value)) {
      return flattenKeys(value as Record<string, unknown>, path);
    }
    return [path];
  });
}

describe("i18n resources", () => {
  it("has both English and Hindi translations", () => {
    expect(Object.keys(resources)).toEqual(expect.arrayContaining(["en", "hi"]));
  });

  it("Hindi has every key English has, and vice versa (Section 5.7: real Hindi+English support)", () => {
    const enKeys = flattenKeys(resources.en.translation).sort();
    const hiKeys = flattenKeys(resources.hi.translation).sort();
    expect(hiKeys).toEqual(enKeys);
  });

  it("no Hindi translation is left as an empty string", () => {
    const hiValues = flattenKeys(resources.hi.translation).map((key) =>
      key.split(".").reduce((obj: any, k) => obj[k], resources.hi.translation)
    );
    for (const value of hiValues) {
      expect(typeof value === "string" && value.trim().length).toBeTruthy();
    }
  });
});
