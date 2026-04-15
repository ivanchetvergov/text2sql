import random
from typing import Any, Callable


class Inserter:
    def __init__(self, conn, rng: random.Random | None = None):
        self.conn = conn
        self.rng = rng or random.Random()

    async def _resolve_dependencies(
        self,
        dependencies: dict[str, str] | None,
        strict_dependencies: bool = True,
    ) -> dict[str, list[Any]]:

        resolved: dict[str, list[Any]] = {}
        if not dependencies:
            return resolved

        for dep_name, dep_query in dependencies.items():
            rows = await self.conn.fetch(dep_query)
            values = [row[0] for row in rows]
            if not values and strict_dependencies:
                raise ValueError(f"Dependency {dep_name} is empty")
            resolved[dep_name] = values

        return resolved

    async def seed(
        self,
        *,
        table: str,
        query: str,
        generator: Callable[[dict[str, Any]], tuple],
        dependencies: dict[str, str] | None = None,
        count: int | None = None,
        per_dependency: str | None = None,
        min_per_dependency: int = 1,
        max_per_dependency: int = 1,
        context_id_key: str = "current_id",
        strict_dependencies: bool = True,
    ) -> int:
        if count is None and per_dependency is None:
            raise ValueError("Specify either count or per_dependency")
        if count is not None and per_dependency is not None:
            raise ValueError("Use count or per_dependency, not both")
        if min_per_dependency > max_per_dependency:
            raise ValueError("min_per_dependency cannot be greater than max_per_dependency")

        deps = await self._resolve_dependencies(dependencies, strict_dependencies)
        items: list[tuple] = []

        if count is not None:
            for _ in range(count):
                items.append(generator(deps))
        else:
            parent_ids = deps.get(per_dependency or "", [])
            for parent_id in parent_ids:
                amount = self.rng.randint(min_per_dependency, max_per_dependency)
                for idx in range(amount):
                    ctx = dict(deps)
                    ctx[context_id_key] = parent_id
                    ctx["current_ordinal"] = idx + 1
                    items.append(generator(ctx))

        if not items:
            print(f"Skip {table}: no items to insert.")
            return 0

        await self.conn.executemany(query, items)
        print(f"Insert {len(items)} items into {table}.")
        return len(items)
