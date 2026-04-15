import random
from faker import Faker


async def seed_participations(inserter, count: int = 50) -> int:
    return await inserter.seed(
        table='participation',
        query=(
            'INSERT INTO participation (user_id, competition_id, team_id, status_id)\n'
            'VALUES ($1, $2, $3, $4)\n'
            'ON CONFLICT (user_id, competition_id) DO NOTHING'
        ),
        generator=lambda deps: (
            random.choice(deps['users']),
            random.choice(deps['competitions']),
            random.choice(deps['teams']),
            random.choice(deps['status']),
        ),
        dependencies={
            'users': 'SELECT user_id FROM "user"',
            'competitions': 'SELECT competition_id FROM competition',
            'teams': 'SELECT team_id FROM team',
            'status': 'SELECT status_id FROM participation_status',
        },
        count=count,
    )

async def seed_configurations(inserter, count: int = 10) -> int:
    return await inserter.seed(
        table='configuration',
        query=(
            'INSERT INTO configuration (metric_id, task_type_id, competition_id, daily_attempt_limit)\n'
            'VALUES ($1, $2, $3, $4)\n'
            'ON CONFLICT (competition_id, metric_id, task_type_id) DO NOTHING'
        ),
        generator=lambda deps: (
            random.choice(deps['metrics']),
            random.choice(deps['task_types']),
            random.choice(deps['competitions']),
            random.randint(1, 100),
        ),
        dependencies={
            'metrics': 'SELECT metric_id FROM metric',
            'task_types': 'SELECT task_type_id FROM task_type',
            'competitions': 'SELECT competition_id FROM competition',
        },
        count=count,
    )

async def seed_competition_datasets(
    inserter,
    min_per_competition: int = 1,
    max_per_competition: int = 3,
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

async def seed_teams(inserter, fake: Faker, count: int = 20) -> int:
    return await inserter.seed(
        table='team',
        query=(
            'INSERT INTO team (competition_id, name, status_id)\n'
            'VALUES ($1, $2, $3)\n'
            'ON CONFLICT (competition_id, name) DO NOTHING'
        ),
        generator=lambda deps: (
            random.choice(deps['competition']),
            fake.company()[:30],
            random.choice(deps['status']),
        ),
        dependencies={
            'competition': 'SELECT competition_id FROM competition',
            'status': 'SELECT status_id FROM team_status',
        },
        count=count,
    )

async def seed_team_members(
    inserter,
    min_per_team: int = 2,
    max_per_team: int = 5,
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

async def seed_team_competitions(
    inserter,
    min_per_team: int = 1,
    max_per_team: int = 2,
) -> int:
    return await inserter.seed(
        table='team_competition',
        query=(
            'INSERT INTO team_competition (team_id, dataset_id)\n'
            'VALUES ($1, $2)\n'
            'ON CONFLICT (team_id, dataset_id) DO NOTHING'
        ),
        generator=lambda deps: (
            deps.get('current_id'),
            random.choice(deps['dataset']),
        ),
        dependencies={
            'team': 'SELECT team_id FROM team',
            'dataset': 'SELECT dataset_id FROM dataset',
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
    await seed_team_competitions(inserter)
    await seed_participations(inserter)
