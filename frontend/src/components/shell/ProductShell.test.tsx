import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProductShell } from "./ProductShell";


describe("ProductShell", () => {
  it("exposes every M8 workbench as accessible navigation", () => {
    const onNavigate = vi.fn();
    render(
      <ProductShell
        active="live"
        onNavigate={onNavigate}
        title="Live Operations"
        subtitle="Decision intelligence"
        status={{ mode: "LIVE", scenario: "lunch", policy: "capr", runId: "run-test" }}
      >
        <div>Workbench body</div>
      </ProductShell>,
    );

    for (const label of ["Live Operations", "Runs", "Dispatch Analysis", "Experiments", "Theory", "Models", "Explorer"]) {
      expect(screen.getByRole("button", { name: new RegExp(`^${label}$`) })).toBeInTheDocument();
    }
    fireEvent.click(screen.getByRole("button", { name: "Explorer" }));
    expect(onNavigate).toHaveBeenCalledWith("explorer");
    expect(screen.getByRole("heading", { name: "Live Operations" })).toBeInTheDocument();
  });
});
