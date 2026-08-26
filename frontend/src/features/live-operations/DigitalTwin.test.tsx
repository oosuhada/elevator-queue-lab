import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Snapshot } from "../../contracts/api";
import { DigitalTwin } from "./DigitalTwin";


function snapshotFixture(): Snapshot {
  const queues = Object.fromEntries(Array.from({ length: 18 }, (_, index) => [String(index + 1), { up: index === 0 ? 3 : 0, down: 0 }]));
  return {
    scenario: "lunch",
    policy: "capr",
    sim_time: 60,
    clock: "12:01:00",
    metrics: {
      avg_wait: 12,
      p95_wait: 30,
      max_wait: 40,
      avg_queue: 2,
      little_law_lq: 2,
      arrival_rate_per_min: 4,
      served: 10,
      arrivals: 15,
      missed_capacity: 0,
      abandoned: 0,
      assignments: 5,
      reassignments: 1,
      invalidations: 0,
      current_queue: 5,
    },
    weights: {},
    elevators: ["L1", "L2", "L3", "H1", "H2", "H3"].map((id, index) => ({
      id,
      bank: id.startsWith("L") ? "low" as const : "high" as const,
      floor: index + 1,
      direction: index % 2 ? 1 : 0,
      load: index,
      capacity: 16,
      stops: [Math.min(18, index + 2)],
      door_open: false,
      phase: "idle",
      target_floor: null,
    })),
    queues,
    calls: [{
      floor: 1,
      direction: 1,
      bank: "low",
      destination: null,
      assigned: "L1",
      wait: 4,
      missed: 0,
      assigned_score: 2.1,
    }],
    history: [],
    audit: {},
    event_tail: [],
    decision_tail: [],
    trace_digest: null,
    simulation_config: {
      floors: 18,
      low_zone_max: 9,
      high_zone_min: 10,
      elevators_per_bank: 3,
      elevator_capacity: 16,
      floor_height_m: 4,
      max_speed_mps: 2.5,
      acceleration_mps2: 1,
      levelling_seconds: 1,
      door_open_seconds: 1,
      door_dwell_seconds: 2,
      door_close_seconds: 1,
      passenger_transfer_seconds: 0.3,
      time_step_seconds: 0.1,
      passenger_patience_seconds: null,
      control_mode: "conventional",
      reassignment_interval_seconds: 2,
      reassignment_cooldown_seconds: 5,
      reassignment_min_gain: 4,
      reassignment_min_eta_gain_seconds: 2,
      max_noncapacity_reassignments_per_call: 1,
      capacity_reserve: 2,
    },
    running: true,
    speed: 20,
    replay_frames: 20,
    saved_replay_available: false,
  };
}

describe("DigitalTwin", () => {
  it("keeps the research building contract visible after the React migration", () => {
    const { container } = render(<DigitalTwin snapshot={snapshotFixture()} />);

    expect(container.querySelectorAll(".floor-line")).toHaveLength(18);
    expect(container.querySelectorAll("[data-car-id]")).toHaveLength(6);
    expect(container.querySelectorAll("#assignment-overlay line")).toHaveLength(1);
    expect(container.querySelector('[data-car-id="L1"]')).toHaveAttribute("data-capacity", "16");
    expect(container.querySelector('[data-car-id="H3"]')).toHaveAttribute("data-floor", "6");
    expect(screen.getByRole("button", { name: "Section" })).toHaveClass("is-active");
    expect(screen.getByRole("button", { name: "2.5D study" })).toBeDisabled();
    expect(screen.getByText(/authoritative 2D section remains fully available/i)).toBeInTheDocument();
  });
});
