BEGIN;


CREATE TABLE IF NOT EXISTS "user" (
    user_id SERIAL PRIMARY KEY,
    role_id INT NOT NULL REFERENCES role(role_id),
    username VARCHAR(20) NOT NULL UNIQUE,
    email VARCHAR(40) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    registered_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS task_type (
    task_type_id SERIAL PRIMARY KEY,
    code VARCHAR(15) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    answer_format VARCHAR(10) NOT NULL,
    validation_schema JSON,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS metric (
    metric_id SERIAL PRIMARY KEY,
    name VARCHAR(10) NOT NULL UNIQUE,
    formula TEXT NOT NULL,
    optimization_dir VARCHAR(3) NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS competition (
    competition_id SERIAL PRIMARY KEY,
    organizer_id INT NOT NULL REFERENCES "user"(user_id),
    status_id INT NOT NULL REFERENCES competition_status(status_id),
    title VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    starts_at TIMESTAMP NOT NULL DEFAULT NOW(),
    ends_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS configuration (
    configuration_id SERIAL PRIMARY KEY,
    competition_id INT NOT NULL REFERENCES competition(competition_id) ON DELETE CASCADE,
    metric_id INT NOT NULL REFERENCES metric(metric_id),
    task_type_id INT NOT NULL REFERENCES task_type(task_type_id),
    daily_attempt_limit SMALLINT NOT NULL DEFAULT 24
);

CREATE TABLE IF NOT EXISTS dataset (
    dataset_id SERIAL PRIMARY KEY,
    purpose_id INT NOT NULL REFERENCES dataset_purpose(purpose_id),
    name VARCHAR(30) NOT NULL,
    is_hidden BOOLEAN NOT NULL DEFAULT FALSE,
    version SMALLINT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS dataset_file (
    file_id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES dataset(dataset_id) ON DELETE CASCADE,
    filename VARCHAR(50) NOT NULL,
    storage_path TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    checksum VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS team (
    team_id SERIAL PRIMARY KEY,
    competition_id INT NOT NULL REFERENCES competition(competition_id) ON DELETE CASCADE,
    status_id INT NOT NULL REFERENCES team_status(status_id),
    name VARCHAR(30) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS participation (
    participation_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
    competition_id INT NOT NULL REFERENCES competition(competition_id) ON DELETE CASCADE,
    status_id INT NOT NULL REFERENCES participation_status(status_id),
    team_id INT REFERENCES team(team_id) ON DELETE SET NULL,
    registered_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS submission (
    submission_id SERIAL PRIMARY KEY,
    participation_id INT NOT NULL REFERENCES participation(participation_id) ON DELETE CASCADE,
    status_id INT NOT NULL REFERENCES submission_status(status_id),
    file_path TEXT NOT NULL,
    attempt_number SMALLINT NOT NULL,
    submitted_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evaluation (
    evaluation_id SERIAL PRIMARY KEY,
    submission_id INT NOT NULL UNIQUE REFERENCES submission(submission_id) ON DELETE CASCADE,
    metric_value NUMERIC(12,6),
    is_valid BOOLEAN NOT NULL DEFAULT FALSE,
    error_log TEXT,
    evaluated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS leaderboard_entry (
    entry_id SERIAL PRIMARY KEY,
    participation_id INT NOT NULL REFERENCES participation(participation_id) ON DELETE CASCADE,
    competition_id INT NOT NULL REFERENCES competition(competition_id) ON DELETE CASCADE,
    best_score NUMERIC(12,6),
    rank SMALLINT,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS solution_code (
    code_id SERIAL PRIMARY KEY,
    submission_id INT NOT NULL UNIQUE REFERENCES submission(submission_id) ON DELETE CASCADE,
    source_code TEXT NOT NULL,
    language VARCHAR(30) NOT NULL,
    description TEXT,
    uploaded_at TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMIT;
