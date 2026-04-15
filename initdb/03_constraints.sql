BEGIN;

-- -----------------------------------------------------------------------
--* CHECK CONSTRAINTS
-- -----------------------------------------------------------------------

ALTER TABLE metric
    ADD CONSTRAINT chk_metric_optimization_dir CHECK (optimization_dir IN ('min', 'max'));

ALTER TABLE competition
    ADD CONSTRAINT chk_competition_dates CHECK (ends_at > starts_at);

ALTER TABLE configuration
    ADD CONSTRAINT chk_configuration_daily_attempt_limit CHECK (daily_attempt_limit > 0);

ALTER TABLE dataset
    ADD CONSTRAINT chk_dataset_version CHECK (version > 0);

ALTER TABLE dataset_file
    ADD CONSTRAINT chk_dataset_file_size CHECK (size_bytes >= 0);

ALTER TABLE submission
    ADD CONSTRAINT chk_submission_attempt_number CHECK (attempt_number > 0);

ALTER TABLE leaderboard_entry
    ADD CONSTRAINT chk_leaderboard_rank CHECK (rank IS NULL OR rank > 0);

-- -----------------------------------------------------------------------
--* UNIQUE CONSTRAINTS
-- -----------------------------------------------------------------------

ALTER TABLE configuration
    ADD CONSTRAINT uq_configuration UNIQUE (competition_id, metric_id, task_type_id);

ALTER TABLE dataset
    ADD CONSTRAINT uq_dataset_name_version UNIQUE (name, version);

ALTER TABLE team
    ADD CONSTRAINT uq_team_name_per_competition UNIQUE (competition_id, name);

ALTER TABLE participation
    ADD CONSTRAINT uq_participation_user_competition UNIQUE (user_id, competition_id);

ALTER TABLE submission
    ADD CONSTRAINT uq_submission_attempt UNIQUE (participation_id, attempt_number);

ALTER TABLE leaderboard_entry
    ADD CONSTRAINT uq_leaderboard_entry UNIQUE (participation_id, competition_id);

COMMIT;
