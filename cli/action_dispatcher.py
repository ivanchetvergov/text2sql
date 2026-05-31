from __future__ import annotations

from faker import Faker

from cli import bootstrap  # noqa: F401
from cli.constants import ACTION_SPECS
from cli.level_distribution import ALL_LEVEL_RATIOS, distribute_total, level_counts
from inserter import Inserter
from seed_base import (
    seed_competitions,
    seed_dataset_files,
    seed_datasets,
    seed_users,
)
from seed_core import (
    seed_competition_datasets,
    seed_configurations,
    seed_participations,
    seed_team_members,
    seed_teams,
)
from seed_dict import run_all_dictionaries
from seed_sub import (
    seed_participation_scores,
    seed_submissions,
)
from seed.settings import (
    COMPETITION_DATASETS_MAX,
    COMPETITION_DATASETS_MIN,
    DATASET_FILES_MAX,
    DATASET_FILES_MIN,
    SUBMISSIONS_PER_PARTICIPATION_MAX,
    SUBMISSIONS_PER_PARTICIPATION_MIN,
    TEAM_COMPETITIONS_MAX,
    TEAM_COMPETITIONS_MIN,
    TEAM_MEMBERS_MAX,
    TEAM_MEMBERS_MIN,
    TEAMS_PER_COMPETITION_MAX,
    TEAMS_PER_COMPETITION_MIN,
)


async def _table_count(conn, table: str) -> int:
    safe_table = table.replace('"', '""')
    return int(await conn.fetchval(f'SELECT COUNT(*)::bigint FROM "{safe_table}"'))


def _bounds_for_target(target_total: int, parent_total: int) -> tuple[int, int]:
    if target_total <= 0 or parent_total <= 0:
        return 0, 0

    exact = target_total / parent_total
    base = int(exact)
    if base <= 0:
        return 0, 1
    if float(base) == exact:
        return base, base
    return base, base + 1


def _clamp_bounds(bounds: tuple[int, int], min_allowed: int, max_allowed: int) -> tuple[int, int]:
    lo, hi = bounds
    lo = max(min_allowed, min(lo, max_allowed))
    hi = max(min_allowed, min(hi, max_allowed))
    if lo > hi:
        lo = hi
    return lo, hi


async def run_level1_from_total(
    conn,
    inserter: Inserter,
    fake: Faker,
    total_count: int,
) -> None:
    counts = level_counts("level1", total_count)

    # Track initial counts
    initial_counts = {
        "user": await _table_count(conn, "user"),
        "dataset": await _table_count(conn, "dataset"),
        "dataset_file": await _table_count(conn, "dataset_file"),
        "competition": await _table_count(conn, "competition"),
    }

    await seed_users(inserter, fake, count=counts["users"])
    await seed_datasets(inserter, fake, count=counts["datasets"])
    datasets_total = await _table_count(conn, "dataset")
    files_min, files_max = _clamp_bounds(
        _bounds_for_target(counts["dataset_files"], datasets_total),
        min_allowed=DATASET_FILES_MIN,
        max_allowed=DATASET_FILES_MAX,
    )
    await seed_dataset_files(
        inserter,
        fake,
        min_per_dataset=files_min,
        max_per_dataset=files_max,
    )
    await seed_competitions(inserter, fake, count=counts["competitions"])

    # Report added counts
    print("\nLevel 1 - Records added:")
    final_counts = {
        "user": await _table_count(conn, "user"),
        "dataset": await _table_count(conn, "dataset"),
        "dataset_file": await _table_count(conn, "dataset_file"),
        "competition": await _table_count(conn, "competition"),
    }
    for table, final in final_counts.items():
        added = final - initial_counts[table]
        print(f"- {table}: +{added}")


async def run_level2_from_total(
    conn,
    inserter: Inserter,
    fake: Faker,
    total_count: int,
) -> None:
    counts = level_counts("level2", total_count)

    # Track initial counts
    initial_counts = {
        "configuration": await _table_count(conn, "configuration"),
        "competition_dataset": await _table_count(conn, "competition_dataset"),
        "team": await _table_count(conn, "team"),
        "team_member": await _table_count(conn, "team_member"),
        "participation": await _table_count(conn, "participation"),
    }

    await seed_configurations(inserter)

    competitions_total = await _table_count(conn, "competition")
    datasets_total = await _table_count(conn, "dataset")
    comp_data_min, comp_data_max = _clamp_bounds(
        _bounds_for_target(
            counts["competition_datasets"],
            competitions_total,
        ),
        min_allowed=COMPETITION_DATASETS_MIN,
        max_allowed=max(COMPETITION_DATASETS_MIN, min(COMPETITION_DATASETS_MAX, datasets_total)),
    )
    await seed_competition_datasets(
        inserter,
        min_per_competition=comp_data_min,
        max_per_competition=comp_data_max,
    )

    await seed_teams(
        inserter,
        fake,
        count=counts["teams"],
    )

    await seed_team_members(
        inserter,
        min_per_team=TEAM_MEMBERS_MIN,
        max_per_team=TEAM_MEMBERS_MAX,
    )

    await seed_participations(inserter)

    # Report added counts
    print("\nLevel 2 - Records added:")
    final_counts = {
        "configuration": await _table_count(conn, "configuration"),
        "competition_dataset": await _table_count(conn, "competition_dataset"),
        "team": await _table_count(conn, "team"),
        "team_member": await _table_count(conn, "team_member"),
        "participation": await _table_count(conn, "participation"),
    }
    for table, final in final_counts.items():
        added = final - initial_counts[table]
        print(f"- {table}: +{added}")


async def run_level3_from_total(
    conn,
    inserter: Inserter,
    fake: Faker,
    total_count: int,
) -> None:
    # Track initial counts
    initial_counts = {
        "submission": await _table_count(conn, "submission"),
        "scored_participation": int(
            await conn.fetchval("SELECT COUNT(*) FROM participation WHERE best_score IS NOT NULL")
        ),
    }

    await seed_submissions(
        inserter,
        fake,
        min_per_participation=SUBMISSIONS_PER_PARTICIPATION_MIN,
        max_per_participation=SUBMISSIONS_PER_PARTICIPATION_MAX,
    )

    await seed_participation_scores(conn)

    # Report added counts
    print("\nLevel 3 - Records added:")
    final_counts = {
        "submission": await _table_count(conn, "submission"),
        "scored_participation": int(
            await conn.fetchval("SELECT COUNT(*) FROM participation WHERE best_score IS NOT NULL")
        ),
    }
    for table, final in final_counts.items():
        added = final - initial_counts[table]
        print(f"- {table}: +{added}")


async def run_all_from_total(
    conn,
    inserter: Inserter,
    fake: Faker,
    total_count: int,
) -> None:
    level_totals = distribute_total(
        total_count,
        ratios=ALL_LEVEL_RATIOS,
    )

    await run_all_dictionaries(conn)
    await run_level1_from_total(conn, inserter, fake, level_totals["level1"])
    await run_level2_from_total(conn, inserter, fake, level_totals["level2"])
    await run_level3_from_total(conn, inserter, fake, level_totals["level3"])


async def print_table_counts(conn) -> None:
    rows = await conn.fetch(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )

    if not rows:
        print("No tables found in public schema.")
        return

    print("Table row counts:")
    table_counts = []
    for row in rows:
        table = row["table_name"]
        safe_table = table.replace('"', '""')
        count = await conn.fetchval(f'SELECT COUNT(*)::bigint FROM "{safe_table}"')
        table_counts.append((table, count))

    # Sort by count in descending order
    table_counts.sort(key=lambda x: x[1], reverse=True)

    total_count = 0
    for table, count in table_counts:
        print(f"- {table}: {count}")
        total_count += count

    print(f"\nTotal records: {total_count}")


async def clear_all_data(conn, *, confirm: str = "NO") -> None:
    if confirm.upper() != "YES":
        raise ValueError("Set confirm=YES to clear all data")

    rows = await conn.fetch(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )

    if not rows:
        print("No tables found in public schema.")
        return

    counts: list[tuple[str, int]] = []
    for row in rows:
        table = row["table_name"]
        safe_table = table.replace('"', '""')
        count = int(await conn.fetchval(f'SELECT COUNT(*)::bigint FROM "{safe_table}"'))
        counts.append((table, count))

    quoted_tables = []
    for table, _ in counts:
        quoted_tables.append('"' + table.replace('"', '""') + '"')
    table_list = ", ".join(quoted_tables)
    await conn.execute(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE")

    total_deleted = sum(count for _, count in counts)
    print("Data cleared for public schema tables:")
    for table, count in counts:
        print(f"- {table}: removed {count}")
    print(f"Total removed rows: {total_deleted}")


async def execute_action(
    action: str,
    *,
    conn,
    inserter: Inserter,
    fake: Faker,
    **kwargs,
) -> int | None:
    if action == "all":
        await run_all_from_total(conn, inserter, fake, total_count=int(kwargs["total_count"]))
        return None
    if action == "dict":
        await run_all_dictionaries(conn)
        return None
    if action == "table_counts":
        await print_table_counts(conn)
        return None
    if action == "clear_all_data":
        await clear_all_data(conn, **kwargs)
        return None
    if action == "level1":
        await run_level1_from_total(conn, inserter, fake, total_count=int(kwargs["total_count"]))
        return None
    if action == "level2":
        await run_level2_from_total(conn, inserter, fake, total_count=int(kwargs["total_count"]))
        return None
    if action == "level3":
        await run_level3_from_total(conn, inserter, fake, total_count=int(kwargs["total_count"]))
        return None
    if action == "users":
        return await seed_users(inserter, fake, **kwargs)
    if action == "datasets":
        return await seed_datasets(inserter, fake, **kwargs)
    if action == "dataset_files":
        return await seed_dataset_files(inserter, fake, **kwargs)
    if action == "competitions":
        return await seed_competitions(inserter, fake, **kwargs)
    if action == "configurations":
        return await seed_configurations(inserter, **kwargs)
    if action == "competition_datasets":
        return await seed_competition_datasets(inserter, **kwargs)
    if action == "teams":
        return await seed_teams(inserter, fake, **kwargs)
    if action == "team_members":
        return await seed_team_members(inserter, **kwargs)
    if action == "participations":
        return await seed_participations(inserter, **kwargs)
    if action == "submissions":
        return await seed_submissions(inserter, fake, **kwargs)
    if action == "participation_scores":
        return await seed_participation_scores(conn)

    raise ValueError(f"Unknown action: {action}")
