BEGIN;

CREATE TABLE IF NOT EXISTS team_member (
    member_id SERIAL PRIMARY KEY,
    team_id INT NOT NULL REFERENCES team(team_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
    team_role_id INT NOT NULL REFERENCES team_role(team_role_id),
    joined_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS competition_dataset (
    competition_id INT NOT NULL REFERENCES competition(competition_id) ON DELETE CASCADE,
    dataset_id INT NOT NULL REFERENCES dataset(dataset_id) ON DELETE CASCADE,
    added_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (competition_id, dataset_id)
);

COMMIT;
