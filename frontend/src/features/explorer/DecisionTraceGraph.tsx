import { useMemo } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import type { DecisionGraphPayload } from "../../contracts/api";


interface DecisionTraceGraphProps {
  graph: DecisionGraphPayload;
  onSelect: (selection: Record<string, unknown> | null) => void;
}

const TYPE_COLUMNS: Record<string, number> = {
  Passenger: 0,
  HallCall: 1,
  DispatchDecision: 2,
  Elevator: 3,
};

export function DecisionTraceGraph({ graph, onSelect }: DecisionTraceGraphProps) {
  const nodes = useMemo<Node[]>(() => {
    const counts = new Map<string, number>();
    return graph.nodes.map((item) => {
      const column = TYPE_COLUMNS[item.type] ?? 4;
      const row = counts.get(item.type) ?? 0;
      counts.set(item.type, row + 1);
      return {
        id: item.id,
        position: { x: column * 245, y: row * 92 },
        data: { label: item.label, ...item.data },
        className: `trace-node trace-node-${item.type.toLowerCase()}`,
        ariaLabel: `${item.type} ${item.label}`,
      };
    });
  }, [graph.nodes]);
  const edges = useMemo<Edge[]>(() => graph.edges.map((item) => ({
    id: item.id,
    source: item.source,
    target: item.target,
    label: item.relation,
    data: { evidence: item.evidence, relation: item.relation },
    className: "trace-edge",
  })), [graph.edges]);

  return (
    <section className="decision-trace-card" data-testid="decision-trace">
      <header className="section-heading">
        <div><span>Decision Trace</span><strong>Evidence graph projection</strong></div>
        <span>{graph.nodes.length} nodes · {graph.edges.length} edges</span>
      </header>
      <div className="decision-trace-graph" aria-label="Interactive dispatch decision graph">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          minZoom={0.25}
          maxZoom={1.8}
          nodesDraggable
          nodesConnectable={false}
          elementsSelectable
          onNodeClick={(_, node) => onSelect({ kind: "node", id: node.id, ...node.data })}
          onEdgeClick={(_, edge) => onSelect({ kind: "edge", id: edge.id, ...edge.data })}
        >
          <Background gap={20} size={1} />
          <MiniMap pannable zoomable />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <details className="graph-alternative">
        <summary>Accessible relationship list</summary>
        <ul>
          {graph.edges.map((edge) => (
            <li key={edge.id}><button type="button" onClick={() => onSelect({ kind: "edge", ...edge })}>{edge.source} → {edge.relation} → {edge.target}</button></li>
          ))}
        </ul>
      </details>
    </section>
  );
}
