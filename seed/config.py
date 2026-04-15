

ROLES = [
    ('admin', 'Administrator with full access'),
    ('админ', 'Администратор с полным доступом'),
    ('organizer', 'Can create and manage competitions'),
    ('организатор', 'Может создавать и управлять соревнованиями'),
    ('participant', 'Can participate in competitions and submit solutions'),
    ('участник', 'Может участвовать в соревнованиях и отправлять решения'),
    ('moderator', 'Can moderate submissions and discussions'),
    ('модератор', 'Может модерировать отправки и дискуссии'),
    ('judge', 'Can evaluate and verify solutions'),
    ('судья', 'Может оценивать и проверять решения')
]

DATASET_PURPOSES = [
    ('train', 'Training data for model optimization'),
    ('обучение', 'Данные для обучения и оптимизации моделей'),
    ('public', 'Data for public leaderboard evaluation'),
    ('публичный', 'Данные  для публичного лидерборда'),
    ('private', 'Data for final private evaluation'),
    ('приватный', 'Данные для приватного лидерборда'),
    ('test', 'Final test set for model validation'),
    ('тест', 'Финальный тестовый набор для валидации')
]

TEAM_ROLES = [
    ('captain', 'Team leader and primary contact'),
    ('капитан', 'Капитан команды и основное контактное лицо'),
    ('member', 'Regular participant in the team'),
    ('участник', 'Обычный участник команды')
]

COMPETITION_STATUSES = [
    ('draft', 'Competition is being prepared'),
    ('черновик', 'Соревнование в процессе подготовки'),
    ('active', 'Competition is currently running'),
    ('активно', 'Соревнование запущено и идет'),
    ('finished', 'Competition has ended'),
    ('завершено', 'Соревнование завершено'),
    ('archived', 'Past competition stored for history'),
    ('архив', 'Прошедшее соревнование в архиве')
]

TEAM_STATUSES = [
    ('active', 'Team is currently participating'),
    ('активна', 'Команда активно участвует'),
    ('inactive', 'Team has withdrawn or is idle'),
    ('неактивна', 'Команда отозвала участие или неактивна'),
    ('disbanded', 'Team is no longer existing'),
    ('распущена', 'Команда расформирована')
]

PARTICIPATION_STATUSES = [
    ('active', 'Participant is allowed to submit'),
    ('активен', 'Участник может отправлять решения'),
    ('inactive', 'Participant is not active in this competition'),
    ('неактивен', 'Участник неактивен в этом соревновании'),
    ('banned', 'Participant is disqualified for rules violation'),
    ('забанен', 'Участник дисквалифицирован за нарушение правил')
]

SUBMISSION_STATUSES = [
    ('queued', 'Submission is waiting for evaluation'),
    ('в_очереди', 'Решение ожидает оценки'),
    ('running', 'Evaluation is in progress'),
    ('выполняется', 'Идет процесс оценки'),
    ('done', 'Successfully evaluated'),
    ('готово', 'Оценка успешно завершена'),
    ('failed', 'Evaluation system error'),
    ('ошибка', 'Ошибка системы оценки')
]

TASK_TYPES = [
    ('classify', 'Classification task (binary or multiclass)', 'csv'),
    ('классификация', 'Задача классификации (бинарная или мультикласс)', 'csv'),
    ('regression', 'Regression task for numerical prediction', 'csv'),
    ('регрессия', 'Задача регрессии для численного прогнозирования', 'csv'),
    ('ranking', 'Task requiring specific item ordering', 'json'),
    ('ранжирование', 'Задача ранжирования', 'json')
]

METRICS = [
    ('accuracy', 'Standard accuracy ratio', 'max'),
    ('rmse', 'Root Mean Squared Error', 'min'),
    ('auc', 'Area Under Curve (ROC)', 'max'),
    ('logloss', 'Logarithmic Loss', 'min')
]

