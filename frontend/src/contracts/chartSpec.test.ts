import { describe, expect, it } from "vitest";
import { parseChartSpec } from "./chartSpec";


describe("ChartSpec runtime validation", () => {
  it("accepts a registered distribution chart", () => {
    const spec = parseChartSpec({
      type: "distribution",
      title: "30-seed AWT distribution",
      source: "evidence/m3-regression-baseline.json",
      metric: "avg_wait",
      groupBy: "policy",
      scenario: "lunch",
      confidenceInterval: true,
    });

    expect(spec.type).toBe("distribution");
    if (spec.type !== "distribution") throw new Error("Expected a distribution ChartSpec");
    expect(spec.scenario).toBe("lunch");
  });

  it("rejects arbitrary component types", () => {
    expect(() => parseChartSpec({ type: "html", title: "Unsafe", source: "planner", html: "<script/>" })).toThrow();
  });

  it("rejects missing evidence source", () => {
    expect(() => parseChartSpec({
      type: "tradeoff",
      title: "Tradeoff",
      x: "energy_proxy",
      y: "avg_wait",
      groupBy: "policy",
      scenario: "evening",
    })).toThrow();
  });
});
