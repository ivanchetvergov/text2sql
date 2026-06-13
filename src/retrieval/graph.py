from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx

from ..utils import GraphReader, Logger

_DEFAULT_CARDINALITY_COST = {
    "one_to_one":  0.0,
    "many_to_one": 0.1,
    "one_to_many": 0.3,
}

_DEFAULT_REVERSE_EDGE_MULTIPLIER = 1.5

_TABLE_ALIASES = {
    "competition_config": "configuration",
    "file_artifact": "dataset_file",
    "leaderboard_row": "participation",
    "leaderboard_entry": "participation",
    "evaluation": "submission",
    "solution_code": "submission",
}


def _canonical_table(name: str) -> str:
    return _TABLE_ALIASES.get(name, name)

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
        """Цепочка FK для добавления в контекст LLM."""
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
    def __init__(self) -> None:
        self._g:          nx.DiGraph              = nx.DiGraph()
        self._tables:     Dict[str, Dict[str, Any]] = {}
        self._algorithms: Dict[str, Any]           = {}
        self._logger = Logger.get_logger("src.graph", filename="graph.log")

    def load_from_dict(self, data: Dict[str, Any]) -> "KnowledgeGraph":
        self._algorithms = data.get("algorithms", {})
        self._tables     = data.get("tables", {})

        for tbl, cfg in self._tables.items():
            self._g.add_node(tbl, hub_score=cfg.get("hub_score", 5), pk=cfg.get("pk"))

        for tbl, cfg in self._tables.items():
            for edge in (cfg.get("edges") or []):
                to          = edge["to"]
                cardinality = edge.get("cardinality", "")
                if to not in self._g:
                    self._g.add_node(to)
                w = self._edge_weight(tbl, to, cardinality)
                attrs = dict(from_col=edge["from_col"], to_col=edge["to_col"],
                             cardinality=cardinality,
                             join_preference=edge.get("join_preference", "JOIN"))
                self._g.add_edge(tbl, to, **attrs, weight=w)
                if not self._g.has_edge(to, tbl):
                    self._g.add_edge(to, tbl, **{**attrs,
                                                 "from_col": edge["to_col"],
                                                 "to_col":   edge["from_col"]},
                                     weight=w * self._reverse_edge_multiplier())

        self._logger.info("Graph loaded: %d nodes, %d edges",
                          self._g.number_of_nodes(), self._g.number_of_edges())
        return self

    def load_from_yaml(self, path: str | Path | None = None) -> "KnowledgeGraph":
        data = GraphReader.load(path)
        raw_tables = data["tables"]
        canonical_tables: Dict[str, Any] = {}
        for tbl, cfg in raw_tables.items():
            ct = _canonical_table(tbl)
            if ct not in canonical_tables:
                canonical_tables[ct] = {**cfg, "edges": []}
            for edge in (cfg.get("edges") or []):
                canonical_tables[ct]["edges"].append({**edge, "to": _canonical_table(edge["to"])})
        return self.load_from_dict({"algorithms": data["algorithms"], "tables": canonical_tables})

    def _hub_score(self, table: str) -> float:
        return float(self._tables.get(table, {}).get("hub_score", 5))

    def _hub_step_cost(self) -> float:
        return float(self._algorithms.get("hub_score_step_cost", 0.12))

    def _cardinality_cost(self, cardinality: str) -> float:
        costs = self._algorithms.get("cardinality_costs", {})
        if cardinality in costs:
            return float(costs[cardinality])
        return _DEFAULT_CARDINALITY_COST.get(cardinality, 0.1)

    def _reverse_edge_multiplier(self) -> float:
        return float(self._algorithms.get("reverse_edge_multiplier",
                                          _DEFAULT_REVERSE_EDGE_MULTIPLIER))

    def _edge_weight(self, from_table: str, to_table: str, cardinality: str) -> float:
        base = 1.0
        mean_hub = (self._hub_score(from_table) + self._hub_score(to_table)) / 2.0
        center_penalty = max(0.0, mean_hub - 1.0) * self._hub_step_cost()
        return base + self._cardinality_cost(cardinality) + center_penalty

    def _path_cost(self, path: List[str]) -> float:
        if len(path) < 2:
            return 0.0
        total = 0.0
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            if self._g.has_edge(a, b):
                total += float(self._g[a][b].get("weight", 1.0))
            else:
                total += 1.0
        return total

    def expand(self, anchor_tables: List[str]) -> List[PathResult]:
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
                cost=self._path_cost(path),
            )]

        self._logger.info("expand: no path found for anchors=%s", anchors)
        return []

    def _bfs_chain(self, anchors: List[str]) -> Optional[List[str]]:
        # Skip isolated nodes (no FK edges) — they can't participate in a join path
        connected = [a for a in anchors if self._g.degree(a) > 0]
        if len(connected) < 2:
            return None

        chain:   List[str] = []
        visited: set[str]  = set()
        for i in range(len(connected) - 1):
            src, dst = connected[i], connected[i + 1]
            if dst in visited:
                continue
            try:
                segment = nx.dijkstra_path(self._g, src, dst, weight="weight")
                for node in (segment if not chain else segment[1:]):
                    if node not in visited:
                        chain.append(node)
                        visited.add(node)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue  # skip disconnected segment, try next pair
        return chain if len(chain) >= 2 else None

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

    def enrich(
        self,
        tables: Dict[str, str],
        ddl_lookup: Optional[Dict[str, str]] = None,
    ) -> tuple[Dict[str, str], str]:
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
        results = self.expand(list(tables.keys()))  # только исходные таблицы RAG, не FK-расширенный набор
        if results:
            pr = results[0]
            hint = pr.to_context_block()
            self._logger.info("Graph hint (BFS):\n%s\n%s\n%s", "-" * 60, hint, "-" * 60)

        return enriched, hint

    def describe(self) -> str:
        lines = [f"Nodes: {self._g.number_of_nodes()}",
                 f"Edges: {self._g.number_of_edges()}"]
        return "\n".join(lines)



if __name__ == "__main__":
    kg = KnowledgeGraph().load_from_yaml()
    print(kg.describe())

    results = kg.expand(["metric", "task_type", "dataset_file"])
    for r in results:
        print(r.to_context_block())

