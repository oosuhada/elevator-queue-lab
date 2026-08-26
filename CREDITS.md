# Credits and Reference Licenses

Elevator Queue Lab's simulator, evidence model, product UI and visual design are original project
work. The following open-source libraries are used in the authored React frontend. Reference
projects listed afterward informed interaction or visual principles only; their source code was not
copied into this repository.

## Runtime Libraries Added for the Portfolio UI Pass

| Project | Usage | License | Upstream |
|---|---|---|---|
| Motion | Bounded car, replay-playhead and score-decomposition motion with reduced-motion support | MIT | https://github.com/motiondivision/motion |
| D3 (`d3-scale`) | Deterministic replay frame-to-ruler scale | ISC | https://github.com/d3/d3-scale |
| xyflow / React Flow | Decision Trace evidence graph; existing dependency substantially refined in this pass | MIT | https://github.com/xyflow/xyflow |
| React Three Fiber | Optional, lazy-loaded 2.5D building-section study | MIT | https://github.com/pmndrs/react-three-fiber |
| Three.js | React Three Fiber runtime/peer dependency | MIT | https://github.com/mrdoob/three.js |

Package distributions retain their upstream license files in the installed dependency tree. This
file records project-level attribution and adoption intent; it does not replace upstream LICENSE
texts.

## Visual / Interaction References

The following projects were reviewed through their README, demo/docs and LICENSE on 2026-08-23.
Only principles were referenced unless the project also appears in the runtime table above.

| Reference | License | Principle reviewed |
|---|---|---|
| Graphite | Apache-2.0 | Dense professional editor hierarchy, structural panels and selection states |
| Excalidraw | MIT | Direct spatial manipulation and inspectable relationships |
| Theatre.js | Apache-2.0 | One timeline coordinating multiple visual systems |
| WebGL Data Globe | MIT | Stable cinematic camera framing around data |
| Drei | MIT | R3F scene/helper patterns; not installed |
| React Postprocessing | MIT | Post-processing trade-offs; rejected for this precision-first UI |
| r3f-scroll-rig | MIT | DOM/WebGL synchronization patterns; not required here |
| Rough.js | MIT | Annotation vocabulary; hand-drawn rendering itself was rejected |
| React Force Graph | MIT | Graph interaction alternative; force layout rejected for deterministic evidence |
| Sigma.js | MIT | Large WebGL graph alternative; unnecessary for the retained decision trace |
| Motion Primitives | MIT | Motion-component patterns; demo endpoint was unavailable during automated review and no code was adopted |

See `docs/reference-adoption.md` for the full investigation, prototype comparison and rejection
rationale, and `docs/visual-reference-catalog.md` for the preserved source catalog.

