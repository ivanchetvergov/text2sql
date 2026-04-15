BEGIN;

CREATE TABLE IF NOT EXISTS role (
    role_id SERIAL PRIMARY KEY,
    name VARCHAR(30) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS dataset_purpose (
    purpose_id SERIAL PRIMARY KEY,
    name VARCHAR(15) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS team_role (
    team_role_id SERIAL PRIMARY KEY,
    name VARCHAR(15) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS competition_status (
    status_id SERIAL PRIMARY KEY,
    name VARCHAR(15) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS team_status (
    status_id SERIAL PRIMARY KEY,
    name VARCHAR(15) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS participation_status (
    status_id SERIAL PRIMARY KEY,
    name VARCHAR(15) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS submission_status (
    status_id SERIAL PRIMARY KEY,
    name VARCHAR(15) NOT NULL UNIQUE,
    description TEXT
);

COMMIT;
