import random
from faker import Faker


async def seed_submissions(
    inserter,
    fake: Faker,
    min_per_participation: int = 1,
    max_per_participation: int = 3,
) -> int:
    return await inserter.seed(
        table='submission',
        query=(
            'INSERT INTO submission (participation_id, status_id, file_path, attempt_number)\n'
            'VALUES ($1, $2, $3, $4)\n'
            'ON CONFLICT (participation_id, attempt_number) DO NOTHING'
        ),
        generator=lambda deps: (
            deps.get('current_id'),
            random.choice(deps['status']),
            fake.file_path(depth=3, extension='zip'),
            deps.get('current_ordinal'),
        ),
        dependencies={
            'participation': 'SELECT participation_id FROM participation',
            'status': 'SELECT status_id FROM submission_status',
        },
        per_dependency='participation',
        min_per_dependency=min_per_participation,
        max_per_dependency=max_per_participation,
    )

async def seed_solution_codes(inserter, fake: Faker) -> int:
    return await inserter.seed(
        table='solution_code',
        query=(
            'INSERT INTO solution_code (submission_id, source_code, language, description)\n'
            'VALUES ($1, $2, $3, $4)\n'
            'ON CONFLICT (submission_id) DO NOTHING'
        ),
        generator=lambda deps: (
            deps.get('current_id'),
            'def solve():\n    return 42\n',
            random.choice(['python', 'cpp', 'java']),
            fake.sentence(nb_words=8)[:200],
        ),
        dependencies={'submission': 'SELECT submission_id FROM submission'},
        per_dependency='submission',
        min_per_dependency=1,
        max_per_dependency=1,
    )

async def seed_evaluations(inserter) -> int:
    return await inserter.seed(
        table='evaluation',
        query=(
            'INSERT INTO evaluation (submission_id, metric_value, is_valid, error_log)\n'
            'VALUES ($1, $2, $3, $4)\n'
            'ON CONFLICT (submission_id) DO NOTHING'
        ),
        generator=lambda deps: (
            deps.get('current_id'),
            round(random.uniform(0.0, 1.0), 6),
            random.choice([True, True, True, False]),
            None,
        ),
        dependencies={'submission': 'SELECT submission_id FROM submission'},
        per_dependency='submission',
        min_per_dependency=1,
        max_per_dependency=1,
    )

async def seed_leaderboard_entries(inserter) -> int:
    return await inserter.seed(
        table='leaderboard_entry',
        query=(
            'INSERT INTO leaderboard_entry (participation_id, competition_id, best_score, rank)\n'
            'VALUES ($1, (SELECT competition_id FROM participation WHERE participation_id = $1), $2, $3)\n'
            'ON CONFLICT (participation_id, competition_id) DO NOTHING'
        ),
        generator=lambda deps: (
            deps.get('current_id'),
            round(random.uniform(0.0, 1.0), 6),
            random.randint(1, 300),
        ),
        dependencies={'participation': 'SELECT participation_id FROM participation'},
        per_dependency='participation',
        min_per_dependency=1,
        max_per_dependency=1,
    )


async def run_level3(inserter, fake: Faker) -> None:
    await seed_submissions(inserter, fake)
    await seed_solution_codes(inserter, fake)
    await seed_evaluations(inserter)
    await seed_leaderboard_entries(inserter)
