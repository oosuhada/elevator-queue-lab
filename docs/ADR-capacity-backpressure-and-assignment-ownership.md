# ADR: Capacity backpressure and assignment ownership

## Status

Accepted as a design constraint for future controller changes.

## Context

The elevator simulator already treats capacity, reassignment and call ownership as first-class model
state. The v0.6 systems capstone made the same pattern explicit in a different domain: producers can
outrun consumers, ownership must be claimed once, and recovery must not silently duplicate logical
work.

## Decision

Controller changes should keep these invariants visible in code and evidence:

- A passenger/call has one current assignment owner at a time.
- A full car pass is not hidden as a successful pickup.
- Reassignment must be recorded as an event with reason and latency.
- Queue pressure should remain observable through queue length, wait percentiles and capacity-miss
  metrics instead of being smoothed away in the UI.
- Any learned or heuristic controller must be compared across common random-number seeds before
  claiming improvement.

## Why this belongs here

This product is already a scheduling/backpressure laboratory. The capstone does not require a code
rewrite; it strengthens the review checklist for controller and UI changes. If a future change hides
capacity misses or mutates assignments without an event, it violates the same ownership principle as
a job runtime that completes work without a durable state transition.

## Non-claims

This ADR does not claim formal elevator safety behavior, ISO/CIBSE compliance, or superiority of any
policy. It only links the product's simulator invariants to the cross-layer systems capstone.
