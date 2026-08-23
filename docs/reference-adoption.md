# Reference Adoption

Reviewed on 2026-08-23 for the **Architectural Section × Kinetic Transit Laboratory** UI pass.
The source catalog is preserved byte-for-byte at `docs/visual-reference-catalog.md`.

The review reopened each candidate repository README and LICENSE through the existing local GitHub
CLI authentication, and checked the linked demo/documentation endpoint where one was available.
No source code was copied from a reference project. Adopted code is consumed through published
packages whose licenses are listed below.

## Adopted in Code

| Reference | License | Files / feature used | What changed in Elevator Queue Lab | Credit location |
|---|---|---|---|---|
| [Motion](https://github.com/motiondivision/motion) | MIT | `DigitalTwin.tsx`, `ReplayTimeline.tsx`, `DecisionInspector.tsx` | Car position, replay playhead, and score-decomposition motion use bounded state transitions and honor reduced-motion preference. Motion never invents state; it interpolates recorded values. | `CREDITS.md` |
| [D3 / d3-scale](https://github.com/d3/d3-scale) | ISC | `ReplayTimeline.tsx` | Converts deterministic replay frame indices into a physical 0–100% ruler so event markers and the selected frame share one scale. Only the modular `d3-scale` package is installed. | `CREDITS.md` |
| [xyflow / React Flow](https://github.com/xyflow/xyflow) | MIT | `DecisionTraceGraph.tsx` | Existing graph use was upgraded from generic draggable nodes to a deterministic evidence pipeline with typed custom nodes, ordered stages, directed smooth-step relationships, focusable elements, read-only topology, provenance notice, and an always-available relationship list. | `CREDITS.md` |
| [React Three Fiber](https://github.com/pmndrs/react-three-fiber) | MIT | `DepthTwinPrototype.tsx`, lazy import in `DigitalTwin.tsx` | Small 2.5D architectural-section study driven by the same `Snapshot`. It is desktop-only, lazy-loaded, and disabled when WebGL or a suitable power profile is unavailable. It is deliberately not the authoritative default. | `CREDITS.md` |

`three` is retained as React Three Fiber's required peer/runtime dependency and is MIT licensed.

## Visual Principles Adopted

| Reference | Observed principle | Our interpretation | Where visible |
|---|---|---|---|
| React Three Fiber examples | Camera and depth should clarify spatial relationships rather than decorate the page. | The optional 2.5D study uses an orthographic section and the exact six-car/floor/queue snapshot, with no ornamental scene objects. | Live Operations → `2.5D study` |
| WebGL Data Globe | A stable camera can give data a physical reading without requiring free-flight controls. | The 2.5D study has a fixed engineering-view camera rather than an exploratory globe-like orbit. | `DepthTwinPrototype.tsx` |
| Graphite | Professional editor hierarchy is expressed through rails, instruments, thin separators, and stateful selection rather than rounded dashboard cards. | The shell now uses title-block typography, structural graphite lines, pale-concrete surfaces, compact instruments, and an evidence inspector. The desktop navigation rail is wide enough for full labels, can be pinned open/closed, and temporarily expands on hover/focus when collapsed. | Product shell, Runs, Explorer, inspector |
| Excalidraw | Spatial relationships remain understandable because selection and connections are direct and inspectable. | Decision Trace keeps direct source→relation→target language and a textual relationship alternative instead of hiding meaning in a visual-only graph. | Explorer → Decision Trace |
| Theatre.js | Timeline position should act as a shared state for the scene. | Replay position now drives the building, metrics/charts, event context, and Decision Inspector from the same saved frame. No Theatre.js dependency was needed. | Live Operations replay |
| Rough.js | Annotation can distinguish evidence from structure. | The idea was narrowed to geometric marker shapes and architectural notation; hand-drawn rendering itself was rejected to avoid a botanical/sketch identity. | Timeline and experiment verdict markers |

## Prototype / Comparison Results

Three implementation directions were compared against real simulator state rather than mock data.

| Prototype | Information readability | Mobile | State accuracy | Performance | Portfolio effect | Accessibility / tests | Decision |
|---|---|---|---|---|---|---|---|
| **2D SVG/CSS architectural section** | Highest: 18 floors, queues, zones, six shafts, cars, links, door/load state are simultaneously readable. | Purpose-built responsive section plus full-screen focus mode. | Direct DOM projection of `Snapshot`; browser check confirmed 18 floor lines, 6 cars, and live assignment links. | No WebGL; default product path. | Strong through section drawing, graphite linework, kinetic cars and title-block notation. | Best: car/floor state remains DOM-addressable and existing Playwright selectors survive. | **Authoritative default** |
| **2.5D React Three Fiber section** | Good spatial impression, but individual numeric/car state is less immediately readable than the section. | Intentionally disabled below 900px. | Same `Snapshot`; no independent scene data. | Lazy chunk; measured ~0.95s from first desktop selection to rendered study on the development Mac. No cost before selection. | Highest depth/camera impact. | Canvas did not expose the six car elements as accessible DOM in the comparison run. | **Keep as optional desktop study only** |
| **Physical replay timeline** | Makes causal events and time position legible without video-player metaphors. | Prioritized before secondary analytics on compact layouts. | Markers are derived from saved replay frames/events; final-frame browser check matched clock and Decision Inspector reason exactly. | DOM/SVG-scale level; no additional rendering surface. | Distinct instrument-panel identity. | Range control remains keyboard accessible; marker buttons have time/kind labels. | **Adopted as core replay UX** |

The 2D/2.5D comparison therefore rejects a 3D-first product. The 2.5D study remains useful as a
portfolio comparison and spatial diagnostic, but accuracy, accessibility, mobile readability and
test compatibility make the architectural 2D section the correct default. The production build
keeps the R3F/Three study in a separate lazy chunk; Vite still reports its uncompressed chunk above
the default 500KB advisory threshold, but that chunk is not requested by the default 2D path.

## Candidate Audit

| Candidate | README / demo / license recheck | License | Outcome |
|---|---|---|---|
| D3 | README and D3 demo reachable | ISC | Adopted modular `d3-scale` only. |
| xyflow | README and demo reachable | MIT | Existing dependency materially upgraded. |
| Motion | README and demo reachable | MIT | Adopted for state motion with reduced-motion handling. |
| Motion Primitives | README and LICENSE readable; automated demo request returned an HTTP error | MIT | Not installed; Motion itself covered the required transitions with less surface area. |
| React Three Fiber | README and examples reachable | MIT | Adopted for the optional 2.5D comparison. |
| Drei | README/docs reachable | MIT | Rejected: primitive geometry/camera needed no helper dependency. |
| React Postprocessing | README/docs reachable | MIT | Rejected: bloom/DOF/noise would reduce engineering legibility and add GPU cost. |
| r3f-scroll-rig | README/repository reachable | MIT | Rejected: the product needs time-state synchronization, not scroll/WebGL synchronization. |
| Rough.js | README/demo reachable | MIT | Rejected as a dependency: hand-drawn rendering conflicts with the precise architectural-section identity. |
| React Force Graph | README/demo reachable | MIT | Rejected: force layout would make the evidence path nondeterministic and harder to scan. |
| Sigma.js | README/demo reachable | MIT | Rejected: WebGL graph scale is unnecessary for the retained run graph and would weaken the accessible alternative. |
| Graphite | README/demo reachable | Apache-2.0 | Visual/editor hierarchy reference only; no source copied. |
| Excalidraw | README/demo reachable | MIT | Spatial manipulation/reference principle only; no dependency needed. |
| Theatre.js | README/demo reachable | Apache-2.0 | Timeline choreography principle adopted, dependency rejected because replay state already supplies the authoritative clock. |
| WebGL Data Globe | README/demo reachable | MIT | Fixed-camera/data-stage principle only; no code copied. |

## Research-Integrity Constraints Kept During Adoption

- The Python simulator, event ledger, deterministic replay and committed evidence remain the source of truth.
- The score-decomposition API change is additive and exposes the exact terms already used by each
  dispatch scorer; the UI does not reverse-engineer or invent a candidate score.
- CAPR is not presented as a global winner. Experiment verdicts distinguish clean win, trade-off,
  regression, insufficient evidence and falsification using committed evidence and shape/text as
  well as color.
- CAPR reassignment has no fabricated numeric “penalty” term. The inspector explicitly shows the
  real cooldown, score-gain, ETA-gain and reassignment-budget gates as gates after scoring.
- The fixed RL result remains negative/mixed and the M7 counterflow threshold remains fuzzy.
- `ChartSpec` continues to gate registered evidence renderers. No arbitrary HTML/JS renderer or
  decorative chart data was introduced.

## Browser Verification Notes

Observed on the local production path `http://127.0.0.1:4173/` after a real shock/CAPR run:

- 1440px: document width 1440px; 18 floors, 6 cars, active assignment links; no console errors.
- 1024px: document width 1024px; no horizontal overflow.
- 390px: document width 390px; selected-event/decision summary visible and building focus control available.
- Replay: event markers present; selected final frame matched both the visible clock and Decision Inspector reason.
- Decision Trace: 66 visible graph nodes and 102 relationship-list buttons in the sampled run; the
  accessible list was open.
- Low-power emulation: 2.5D disabled and six-car 2D section preserved, no console errors.
- WebGL-off emulation: 2.5D disabled and six-car 2D section preserved, no console errors.
- `prefers-reduced-motion: reduce`: recognized by the browser; section remained functional with six cars.

Counts above describe the sampled retained run and are verification evidence, not hard-coded UI data.

## License Verification

- [x] LICENSE opened and read for every candidate in the audit table.
- [x] README opened and reviewed for every candidate in the audit table.
- [x] Demo/docs endpoint checked where one was available.
- [x] Attribution and dependency license information recorded in `CREDITS.md`.
- [x] No unknown-license code copied.
- [x] No incompatible copyleft dependency introduced.
- [x] Unused candidates were not installed.

