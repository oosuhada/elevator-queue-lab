import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
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
  Pickup: 4,
  WaitMetric: 5,
};

const TYPE_SYMBOLS: Record<string, string> = {
  Passenger: "P",
  HallCall: "↕",
  DispatchDecision: "D",
  Elevator: "E",
  Pickup: "↑",
  WaitMetric: "W",
};

interface TraceNodeData extends Record<string, unknown> {
  label: string;
  type: string;
}

function TraceNode({ data, selected }: NodeProps<Node<TraceNodeData>>) {
  const symbol = TYPE_SYMBOLS[data.type] ?? "·";
  return (
    <div className={`trace-node-body trace-kind-${data.type.toLowerCase()} ${selected ? "is-selected" : ""}`}>
      <Handle type="target" position={Position.Left} className="trace-handle" />
      <span className="trace-node-symbol" aria-hidden="true">{symbol}</span>
      <span className="trace-node-copy"><small>{data.type}</small><strong>{data.label}</strong></span>
      <Handle type="source" position={Position.Right} className="trace-handle" />
    </div>
  );
}

const nodeTypes = { evidence: TraceNode };

export function DecisionTraceGraph({ graph, onSelect }: DecisionTraceGraphProps) {
  const nodes = useMemo<Node<TraceNodeData>[]>(() => {
    const counts = new Map<string, number>();
    return graph.nodes.map((item) => {
      const column = TYPE_COLUMNS[item.type] ?? 5;
      const row = counts.get(item.type) ?? 0;
      counts.set(item.type, row + 1);
      return {
        id: item.id,
        type: "evidence",
        position: { x: column * 245, y: row * 94 },
        data: { label: item.label, type: item.type, ...item.data },
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
    className: `trace-edge trace-edge-${item.relation.replaceAll("_", "-")}`,
    type: "smoothstep",
    markerEnd: { type: MarkerType.ArrowClosed, width: 13, height: 13 },
  })), [graph.edges]);

  return (
    <section className="decision-trace-card" data-testid="decision-trace">
      <header className="section-heading">
        <div><span>Decision Trace / xyflow projection</span><strong>Passenger → call → evaluation → car → outcome</strong></div>
        <span>{graph.nodes.length} nodes · {graph.edges.length} edges · read-only</span>
      </header>
      <div className="trace-stage-labels" aria-hidden="true"><span>DEMAND</span><span>CALL</span><span>DECISION</span><span>CAR</span><span>OUTCOME</span></div>
      <div className="decision-trace-graph" aria-label="Interactive dispatch decision graph">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.22 }}
          minZoom={0.25}
          maxZoom={1.8}
          nodesDraggable={false}
          nodesConnectable={false}
          nodesFocusable
          edgesFocusable
          elementsSelectable
          panOnScroll
          selectionOnDrag={false}
          onNodeClick={(_, node) => onSelect({ kind: "node", id: node.id, ...node.data })}
          onEdgeClick={(_, edge) => onSelect({ kind: "edge", id: edge.id, ...edge.data })}
        >
          <Background variant={BackgroundVariant.Lines} gap={24} size={0.7} />
          <MiniMap pannable zoomable nodeStrokeWidth={2} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <div className="graph-provenance-note">Graph topology is a deterministic read-only projection of simulator state, decision history and the event ledger. It is not a secondary graph database.</div>
      <details className="graph-alternative" open>
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
