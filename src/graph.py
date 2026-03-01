from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx

from .utils import GraphReader, Logger

class JoinEdge:
    __slots__ = ("from_table", "to_table", "from_col", "to_col",
                 "cardinality", "join_preference")

    def __init__(self, from_table: str, to_table: str,
                 from_col: str, to_col: str,
                 cardinality: str, join_preference: str):
        self.from_table     = from_table
        self.to_table       = to_table
        self.from_col       = from_col
        self.to_col         = to_col
        self.cardinality    = cardinality
        self.join_preference = join_preference

    def sql_clause(self, from_alias: str, to_alias: str) -> str:
        return (f"{self.join_preference} {self.to_table} {to_alias}"
                f" ON {to_alias}.{self.to_col} = {from_alias}.{self.from_col}")


class PathResult:
    def __init__(self, tables: List[str], edges: List[JoinEdge], cost: float):
        self.tables = tables
        self.edges  = edges
        self.cost   = cost

    def to_context_block(self) -> str:
        """FK chain for injection into LLM context."""
        lines = ["Tables: " + " → ".join(self.tables)]
        if self.edges:
            lines.append("Joins:")
            for e in self.edges:
                lines.append(
                    f"  {e.join_preference} {e.to_table}"
                    f" ON {e.to_table}.{e.to_col} = {e.from_table}.{e.from_col}"
                )
        return "\n".join(lines)


class KnowledgeGraph:
    def __init__(self):
        self._g: nx.DiGraph = nx.DiGraph()
        self._tables:     Dict[str, Dict[str, Any]] = {}
        self._algorithms: Dict[str, Any] = {}
        self._logger = Logger.get_logger("src.graph", filename="graph.log")


    def load_from_yaml(self, path: Optional[str | Path] = None) -> "KnowledgeGraph":
        data = GraphReader.load(path)
        self._algorithms = data["algorithms"]
        self._tables     = data["tables"]

        for tbl, cfg in self._tables.items():
            cost = self._node_cost(cfg.get("node_type", ""))
            self._g.add_node(tbl,
                             node_type=cfg.get("node_type", ""),
                             hub_score=cfg.get("hub_score", 5),
                             pk=cfg.get("pk"),
                             cost=cost)

        for tbl, cfg in self._tables.items():
            for edge in (cfg.get("edges") or []):
                to = edge["to"]
                if to not in self._g:
                    self._g.add_node(to, cost=1.0)
                w = (self._node_cost(self._tables.get(to, {}).get("node_type", "")) +
                     self._node_cost(cfg.get("node_type", ""))) / 2.0
                self._g.add_edge(tbl, to,
                                 from_col=edge["from_col"],
                                 to_col=edge["to_col"],
                                 cardinality=edge.get("cardinality", ""),
                                 join_preference=edge.get("join_preference", "JOIN"),
                                 weight=w)

                if not self._g.has_edge(to, tbl):
                    self._g.add_edge(to, tbl,
                                     from_col=edge["to_col"],
                                     to_col=edge["from_col"],
                                     cardinality=edge.get("cardinality", ""),
                                     join_preference=edge.get("join_preference", "JOIN"),
                                     weight=w * 1.5)

        self._logger.info("Graph loaded: %d nodes, %d edges",
                          self._g.number_of_nodes(), self._g.number_of_edges())
        return self

    def _node_cost(self, node_type: str) -> float:
        return self._algorithms.get("node_type_costs", {}).get(node_type, 1.0)


    def expand(self, anchor_tables: List[str], question: str = "", k: int = 1) -> List[PathResult]:
        anchors = [t for t in anchor_tables if t in self._g]
        if not anchors:
            self._logger.warning("No anchors found in graph: %s", anchor_tables)
            return []

        path = self._bfs_chain(anchors)
        if path:
            self._logger.info("expand: BFS path=%s", path)
            return [PathResult(
                tables=path,
                edges=self._edges_for_path(path),
                cost=float(len(path)),
            )]

        self._logger.info("expand: no path found for anchors=%s", anchors)
        return []

    def _bfs_chain(self, anchors: List[str]) -> Optional[List[str]]:
        """Dijkstra-shortest path chaining through ordered anchors."""
        max_len = self._algorithms.get("max_path_length", 5)
        chain: List[str] = []
        for i in range(len(anchors) - 1):
            try:
                segment = nx.dijkstra_path(self._g, anchors[i], anchors[i + 1], weight="weight")
                if len(segment) > max_len:
                    self._logger.info("BFS: segment %s→%s exceeds max_path_length=%d",
                                      anchors[i], anchors[i + 1], max_len)
                    return None
                chain.extend(segment if not chain else segment[1:])
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                return None
        return chain

    def _edges_for_path(self, tables: List[str]) -> List[JoinEdge]:
        edges = []
        for i in range(len(tables) - 1):
            a, b = tables[i], tables[i + 1]
            if self._g.has_edge(a, b):
                d = self._g[a][b]
                edges.append(JoinEdge(a, b, d["from_col"], d["to_col"],
                                      d.get("cardinality", ""),
                                      d.get("join_preference", "JOIN")))
        return edges

    def _is_leaf(self, table: str) -> bool:
        return self._tables.get(table, {}).get("hub_score", 5) >= 5

    def _schema_hints_block(self, table_names: List[str]) -> str:
        lines: List[str] = []
        for tname in table_names:
            cfg = self._tables.get(tname, {})
            parts: List[str] = []

            for h in (cfg.get("filter_hints") or []):
                parts.append(f"filter {h['col']} ({h['usage']})")

            agg = cfg.get("aggregation_hints") or {}
            if agg.get("aggregate_cols"):
                parts.append("aggregate: " + ", ".join(agg["aggregate_cols"]))
            if agg.get("group_by"):
                parts.append("group_by: " + ", ".join(agg["group_by"]))

            if parts:
                lines.append(f"  {tname}: " + " | ".join(parts))
        return ("## Schema hints\n" + "\n".join(lines)) if lines else ""

    def enrich(
        self,
        tables: Dict[str, str],
        question: str,
        ddl_lookup: Optional[Dict[str, str]] = None,
    ) -> tuple:
        enriched = dict(tables)
        lookup   = ddl_lookup or {}

        added: List[str] = []
        for tname in list(tables.keys()):
            for neighbor in self._g.successors(tname):
                if neighbor in enriched or self._is_leaf(neighbor):
                    continue
                ctx = lookup.get(neighbor, "")
                if not ctx:
                    pk  = self._tables.get(neighbor, {}).get("pk", "")
                    ctx = f"{neighbor}({pk} PK)" if pk else neighbor
                enriched[neighbor] = ctx
                added.append(neighbor)
        if added:
            self._logger.info("FK expansion added: %s", added)

        hint = ""
        results = self.expand(list(enriched.keys()), question=question)
        if results:
            pr = results[0]
            hint = pr.to_context_block()
            fanout = [f"  {e.from_table} → {e.to_table}" for e in pr.edges
                      if e.cardinality == "one_to_many"]
            if fanout:
                hint += "\nFan-out risk (one_to_many — consider subquery):\n" + "\n".join(fanout)
            self._logger.info("Graph hint (BFS):\n%s\n%s\n%s", "-" * 60, hint, "-" * 60)

        schema_hints = self._schema_hints_block(list(enriched.keys()))
        return enriched, hint, schema_hints

    def search_by_node_type(self, node_type: str) -> List[str]:
        return [n for n, d in self._g.nodes(data=True)
                if d.get("node_type") == node_type]

    def describe(self) -> str:
        lines = [f"Nodes: {self._g.number_of_nodes()}",
                 f"Edges: {self._g.number_of_edges()}"]
        return "\n".join(lines)



if __name__ == "__main__":
    kg = KnowledgeGraph().load_from_yaml()
    kg.show()
    print(kg.describe())

    results = kg.expand(["metric", "task_type", "file_artifact"], question="среднее accuracy классификация")
    for r in results:
        print(r.to_context_block())

