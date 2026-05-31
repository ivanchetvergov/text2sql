BEGIN;

CREATE INDEX IF NOT EXISTS idx_participation_team_id ON participation(team_id);
CREATE INDEX IF NOT EXISTS idx_participation_competition_id ON participation(competition_id);

CREATE INDEX IF NOT EXISTS idx_submission_participation_id ON submission(participation_id);

CREATE INDEX IF NOT EXISTS idx_team_member_team_id ON team_member(team_id);
CREATE INDEX IF NOT EXISTS idx_team_member_user_id ON team_member(user_id);

CREATE INDEX IF NOT EXISTS idx_competition_dataset_competition_id ON competition_dataset(competition_id);
CREATE INDEX IF NOT EXISTS idx_competition_dataset_dataset_id ON competition_dataset(dataset_id);

CREATE INDEX IF NOT EXISTS idx_configuration_competition_id ON configuration(competition_id);

COMMIT;
