import random
from faker import Faker

from seed.constants import TEAM_NAMES, TEAM_SUFFIXES
from seed.settings import (
    COMPETITION_DATASETS_MAX,
    COMPETITION_DATASETS_MIN,
    TEAM_COMPETITIONS_MAX,
    TEAM_COMPETITIONS_MIN,
    TEAM_MEMBERS_MAX,
    TEAM_MEMBERS_MIN,
    TEAMS_PER_COMPETITION_MAX,
    TEAMS_PER_COMPETITION_MIN,
)

async def seed_participations(
    inserter,
    min_competitions_per_team: int = TEAM_COMPETITIONS_MIN,
    max_competitions_per_team: int = TEAM_COMPETITIONS_MAX,
) -> int:
    teams = await inserter.conn.fetch("SELECT team_id FROM team")
    competitions = await inserter.conn.fetch("SELECT competition_id FROM competition")
    members = await inserter.conn.fetch("SELECT team_id, user_id FROM team_member")
    statuses = await inserter.conn.fetch("SELECT status_id FROM participation_status")

    if not teams or not competitions or not members or not statuses:
        print("Skip participation: dependencies are empty")
        return 0

    team_members_map = {}
    for m in members:
        team_members_map.setdefault(m['team_id'], []).append(m['user_id'])

    status_ids = [s['status_id'] for s in statuses]
    comp_ids = [c['competition_id'] for c in competitions]

    items = []
    for t in teams:
        t_id = t['team_id']
        t_members = team_members_map.get(t_id, [])
        if not t_members:
            continue

        num_comps = inserter.rng.randint(min_competitions_per_team, max_competitions_per_team)
        chosen_comps = inserter.rng.sample(comp_ids, min(num_comps, len(comp_ids)))

        for c_id in chosen_comps:
            items.append((
                c_id,
                t_id,
                inserter.rng.choice(status_ids),
                None,
                None,
            ))

    if not items:
        return 0

    query = (
        'INSERT INTO participation (competition_id, team_id, status_id, best_score, rank)\n'
        'VALUES ($1, $2, $3, $4, $5)\n'
        'ON CONFLICT (team_id, competition_id) DO NOTHING'
    )

    inserted = 0
    batch_size = 2000
    for start in range(0, len(items), batch_size):
        chunk = items[start:start + batch_size]
        await inserter.conn.executemany(query, chunk)
        inserted += len(chunk)

    print(f"Insert {inserted} items into participation.")
    return inserted

async def seed_configurations(inserter) -> int:
    return await inserter.seed(
        table='configuration',
        query=(
            'INSERT INTO configuration (metric_id, task_type_id, competition_id, daily_attempt_limit)\n'
            'VALUES ($1, $2, $3, $4)\n'
            'ON CONFLICT (competition_id, metric_id, task_type_id) DO NOTHING'
        ),
        generator=lambda deps: (
            deps['metrics'][deps.get('current_id') % len(deps['metrics'])],
            deps['task_types'][deps.get('current_id') % len(deps['task_types'])],
            deps.get('current_id'),
            random.randint(12, 48),
        ),
        dependencies={
            'competitions': (
                'SELECT c.competition_id\n'
                'FROM competition c\n'
                'LEFT JOIN configuration cfg ON cfg.competition_id = c.competition_id\n'
                'WHERE cfg.competition_id IS NULL\n'
                'ORDER BY c.competition_id'
            ),
            'metrics': 'SELECT metric_id FROM metric',
            'task_types': 'SELECT task_type_id FROM task_type',
        },
        per_dependency='competitions',
        min_per_dependency=1,
        max_per_dependency=1,
    )

async def seed_competition_datasets(
    inserter,
    min_per_competition: int = COMPETITION_DATASETS_MIN,
    max_per_competition: int = COMPETITION_DATASETS_MAX,
) -> int:
    return await inserter.seed(
        table='competition_dataset',
        query=(
            'INSERT INTO competition_dataset (competition_id, dataset_id)\n'
            'VALUES ($1, $2)\n'
            'ON CONFLICT (competition_id, dataset_id) DO NOTHING'
        ),
        generator=lambda deps: (
            deps.get('current_id'),
            random.choice(deps['dataset']),
        ),
        dependencies={
            'competition': 'SELECT competition_id FROM competition',
            'dataset': 'SELECT dataset_id FROM dataset',
        },
        per_dependency='competition',
        min_per_dependency=min_per_competition,
        max_per_dependency=max_per_competition,
    )

async def seed_teams(
    inserter,
    fake: Faker,
    count: int = 50,
) -> int:
    return await inserter.seed(
        table='team',
        query=(
            'INSERT INTO team (name, status_id)\n'
            'VALUES ($1, $2)\n'
            'ON CONFLICT (name) DO NOTHING'
        ),
        generator=lambda deps: (
            f"{random.choice(TEAM_NAMES)} {random.choice(TEAM_SUFFIXES)} {random.randint(1, 999999)}"[:30],
            random.choice(deps['status']),
        ),
        dependencies={
            'status': 'SELECT status_id FROM team_status',
        },
        count=count,
    )

async def seed_team_members(
    inserter,
    min_per_team: int = TEAM_MEMBERS_MIN,
    max_per_team: int = TEAM_MEMBERS_MAX,
) -> int:
    return await inserter.seed(
        table='team_member',
        query=(
            'INSERT INTO team_member (team_id, user_id, team_role_id)\n'
            'VALUES ($1, $2, $3)'
        ),
        generator=lambda deps: (
            deps.get('current_id'),
            random.choice(deps['users']),
            random.choice(deps['roles']),
        ),
        dependencies={
            'team': 'SELECT team_id FROM team',
            'users': 'SELECT user_id FROM "user"',
            'roles': 'SELECT team_role_id FROM team_role',
        },
        per_dependency='team',
        min_per_dependency=min_per_team,
        max_per_dependency=max_per_team,
    )

async def run_level2(inserter, fake: Faker) -> None:
    await seed_configurations(inserter)
    await seed_competition_datasets(inserter)
    await seed_teams(inserter, fake)
    await seed_team_members(inserter)
    await seed_participations(inserter)
