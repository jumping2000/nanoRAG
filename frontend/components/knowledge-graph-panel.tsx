"use client";

import { LoaderCircle, Network, RefreshCcw, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { GraphEdge, GraphNode, GraphSnapshot } from "@/lib/types";
import { cn, getErrorMessage } from "@/lib/utils";
import { getKnowledgeGraph } from "@/services/api";

type KnowledgeGraphPanelProps = {
  kbId: string;
};

type PositionedNode = {
  node: GraphNode;
  x: number;
  y: number;
};

const GRAPH_WIDTH = 280;
const GRAPH_HEIGHT = 240;

export function KnowledgeGraphPanel({ kbId }: KnowledgeGraphPanelProps) {
  const [snapshot, setSnapshot] = useState<GraphSnapshot | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [searchValue, setSearchValue] = useState("");
  const [minWeight, setMinWeight] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setSelectedNodeId("");
    setSearchValue("");
    void loadGraph(minWeight);
  }, [kbId]);

  useEffect(() => {
    void loadGraph(minWeight);
  }, [minWeight]);

  async function loadGraph(nextMinWeight: number) {
    setIsLoading(true);
    setError("");
    try {
      const nextSnapshot = await getKnowledgeGraph(kbId, { limit: 18, minWeight: nextMinWeight });
      setSnapshot(nextSnapshot);
      setSelectedNodeId((current) => {
        if (current && nextSnapshot.nodes.some((node) => node.id === current)) {
          return current;
        }
        return nextSnapshot.nodes[0]?.id ?? "";
      });
    } catch (nextError) {
      setError(getErrorMessage(nextError, "Unable to load graph"));
      setSnapshot(null);
      setSelectedNodeId("");
    } finally {
      setIsLoading(false);
    }
  }

  if (isLoading) {
    return (
      <div className="mt-5 flex min-h-[320px] items-center justify-center rounded-[1.6rem] border border-border/75 bg-background/60">
        <div className="flex items-center gap-2 text-sm text-foreground/60">
          <LoaderCircle className="size-4 animate-spin" />
          Building knowledge graph...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mt-5 rounded-[1.6rem] border border-red-500/20 bg-red-500/5 p-5">
        <p className="text-sm font-medium text-red-700 dark:text-red-300">Graph unavailable</p>
        <p className="mt-2 text-sm text-red-700/80 dark:text-red-300/80">{error}</p>
        <Button type="button" variant="outline" className="mt-4" onClick={() => void loadGraph(minWeight)}>
          <RefreshCcw className="size-4" />
          Retry
        </Button>
      </div>
    );
  }

  if (!snapshot || !snapshot.nodes.length) {
    return (
      <div className="mt-5 rounded-[1.6rem] border border-dashed border-border/80 bg-background/65 p-6 text-center">
        <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-primary/12 text-primary">
          <Network className="size-5" />
        </div>
        <h3 className="mt-4 text-base font-medium">No graph facts yet</h3>
        <p className="mt-2 text-sm text-foreground/55">
          Upload documents containing named systems, services, tools, or organizations to extract entity relations.
        </p>
      </div>
    );
  }

  const view = buildGraphView(snapshot, searchValue, selectedNodeId);
  const selectedNode = view.nodes.find((item) => item.id === (selectedNodeId || view.nodes[0]?.id));
  const relatedEdges = selectedNode
    ? view.edges.filter((edge) => edge.source === selectedNode.id || edge.target === selectedNode.id)
    : [];
  const layout = createCircularLayout(view.nodes);

  return (
    <div className="mt-5 space-y-4">
      <div className="grid grid-cols-3 gap-2 text-xs text-foreground/60">
        <GraphMetric label="Nodes" value={String(snapshot.stats.nodes)} />
        <GraphMetric label="Edges" value={String(snapshot.stats.edges)} />
        <GraphMetric label="Mentions" value={String(snapshot.stats.mentions)} />
      </div>

      <div className="flex items-center gap-2 rounded-2xl border border-border/80 bg-background/65 px-3 py-2">
        <Search className="size-4 text-foreground/45" />
        <input
          value={searchValue}
          onChange={(event) => setSearchValue(event.target.value)}
          placeholder="Find entity"
          className="w-full bg-transparent text-sm outline-none placeholder:text-foreground/35"
        />
      </div>

      <div className="flex items-center justify-between gap-2">
        <label className="flex items-center gap-2 text-xs text-foreground/55">
          Min edge weight
          <select
            value={minWeight}
            onChange={(event) => setMinWeight(Number(event.target.value))}
            className="rounded-xl border border-border/80 bg-background/70 px-2 py-1 text-xs"
          >
            <option value={1}>1+</option>
            <option value={2}>2+</option>
            <option value={3}>3+</option>
          </select>
        </label>
        <Button type="button" variant="outline" size="sm" onClick={() => void loadGraph(minWeight)}>
          <RefreshCcw className="size-4" />
          Refresh
        </Button>
      </div>

      <div className="rounded-[1.6rem] border border-border/75 bg-background/65 p-3">
        <svg viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`} className="h-[240px] w-full">
          {view.edges.map((edge) => {
            const source = layout.find((item) => item.node.id === edge.source);
            const target = layout.find((item) => item.node.id === edge.target);
            if (!source || !target) {
              return null;
            }
            const isActive = selectedNode ? edge.source === selectedNode.id || edge.target === selectedNode.id : false;
            return (
              <g key={edge.id}>
                <line
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  stroke={isActive ? "hsl(var(--primary))" : "currentColor"}
                  strokeOpacity={isActive ? 0.6 : 0.22}
                  strokeWidth={1 + Math.min(edge.weight, 4)}
                />
                <text
                  x={(source.x + target.x) / 2}
                  y={(source.y + target.y) / 2 - 4}
                  textAnchor="middle"
                  className="fill-foreground/45 text-[8px] uppercase tracking-[0.18em]"
                >
                  {edge.predicate.replaceAll("_", " ")}
                </text>
              </g>
            );
          })}
          {layout.map(({ node, x, y }) => {
            const isSelected = node.id === (selectedNode?.id ?? "");
            return (
              <g key={node.id} onClick={() => setSelectedNodeId(node.id)} className="cursor-pointer">
                <circle
                  cx={x}
                  cy={y}
                  r={12 + Math.min(node.mentions, 5)}
                  fill={nodeColor(node.entity_type)}
                  stroke={isSelected ? "hsl(var(--primary))" : "transparent"}
                  strokeWidth={isSelected ? 3 : 0}
                />
                <text x={x} y={y + 28} textAnchor="middle" className="fill-foreground text-[10px] font-medium">
                  {truncateLabel(node.label)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {selectedNode ? (
        <div className="rounded-[1.6rem] border border-border/75 bg-background/70 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium">{selectedNode.label}</p>
              <p className="mt-1 text-xs text-foreground/55">{selectedNode.entity_type} · {selectedNode.mentions} mentions</p>
            </div>
            <Badge>{relatedEdges.length} links</Badge>
          </div>

          <div className="mt-4 space-y-3">
            {relatedEdges.length ? (
              relatedEdges.map((edge) => {
                const counterpart = edge.source === selectedNode.id ? view.nodeMap[edge.target] : view.nodeMap[edge.source];
                return (
                  <div key={edge.id} className="rounded-2xl border border-border/70 bg-card/75 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium">
                        {edge.predicate.replaceAll("_", " ")} · {counterpart?.label ?? "Unknown"}
                      </p>
                      <Badge>{edge.weight}</Badge>
                    </div>
                    {edge.evidence.slice(0, 2).map((item) => (
                      <div key={`${edge.id}-${item.chunk_id}`} className="mt-3 rounded-2xl bg-background/70 p-3 text-xs text-foreground/70">
                        <p className="font-medium text-foreground/85">{item.filename}</p>
                        <p className="mt-1">page {item.page ?? "-"} · section {item.section ?? "-"}</p>
                        <p className="mt-2 leading-5">{item.snippet}</p>
                      </div>
                    ))}
                  </div>
                );
              })
            ) : (
              <p className="text-sm text-foreground/55">No connected relations in the current graph window.</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function GraphMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/75 bg-background/65 px-3 py-2 text-center">
      <p className="text-[10px] uppercase tracking-[0.2em]">{label}</p>
      <p className="mt-1 text-sm font-medium text-foreground/85">{value}</p>
    </div>
  );
}

function buildGraphView(snapshot: GraphSnapshot, searchValue: string, selectedNodeId: string) {
  const normalizedQuery = searchValue.trim().toLowerCase();
  const baseNodeIds = new Set<string>();

  if (normalizedQuery) {
    for (const node of snapshot.nodes) {
      if (node.label.toLowerCase().includes(normalizedQuery)) {
        baseNodeIds.add(node.id);
      }
    }
  }

  if (!baseNodeIds.size && selectedNodeId) {
    baseNodeIds.add(selectedNodeId);
  }

  if (!baseNodeIds.size) {
    for (const node of snapshot.nodes.slice(0, 8)) {
      baseNodeIds.add(node.id);
    }
  }

  const visibleNodeIds = new Set(baseNodeIds);
  for (const edge of snapshot.edges) {
    if (baseNodeIds.has(edge.source) || baseNodeIds.has(edge.target)) {
      visibleNodeIds.add(edge.source);
      visibleNodeIds.add(edge.target);
    }
  }

  const nodes = snapshot.nodes.filter((node) => visibleNodeIds.has(node.id));
  const edges = snapshot.edges.filter(
    (edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target),
  );
  const nodeMap = Object.fromEntries(nodes.map((node) => [node.id, node]));

  return { nodes, edges, nodeMap };
}

function createCircularLayout(nodes: GraphNode[]): PositionedNode[] {
  if (!nodes.length) {
    return [];
  }
  if (nodes.length === 1) {
    return [{ node: nodes[0], x: GRAPH_WIDTH / 2, y: GRAPH_HEIGHT / 2 }];
  }

  const centerX = GRAPH_WIDTH / 2;
  const centerY = GRAPH_HEIGHT / 2;
  const radius = Math.min(GRAPH_WIDTH, GRAPH_HEIGHT) / 2 - 32;

  return nodes.map((node, index) => {
    const angle = (Math.PI * 2 * index) / nodes.length - Math.PI / 2;
    return {
      node,
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius,
    };
  });
}

function nodeColor(entityType: string) {
  switch (entityType) {
    case "database":
      return "#0f766e";
    case "service":
      return "#2563eb";
    case "system":
      return "#7c3aed";
    case "organization":
      return "#b45309";
    default:
      return "#475569";
  }
}

function truncateLabel(label: string) {
  return label.length > 16 ? `${label.slice(0, 13)}...` : label;
}