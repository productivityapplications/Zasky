-- Manual sandbox owner seed for the SQLite judge database.
--
-- The application normally creates this row automatically when it boots
-- with SANDBOX_DATABASE_URL set. Run this only if you need to recreate the
-- sandbox owner manually:
--
--   sqlite3 data/sandbox.db < scripts/sandbox-owner.sql
--
-- Replace sandbox-room with the Switch room ID mapped to #judges-sandbox.
-- The dummy Discord participant ID is intentionally not a real account.

INSERT INTO owner_config (
    id,
    owner_switch_participant_id,
    allowed_room_id,
    timezone,
    capacity_pct,
    week_start_weekday,
    daily_task_limit,
    transition_buffer_min,
    morning_prep_min,
    commute_buffer_min,
    availability_json,
    morning_prompt_time,
    evening_prompt_time,
    reminders_enabled,
    timebox_checkins_enabled,
    revision,
    created_at,
    updated_at
) VALUES (
    1,
    '@sandbox:judge',
    'sandbox-room',
    'Africa/Lagos',
    65,
    'monday',
    3,
    10,
    30,
    0,
    '{"monday":[{"start":"09:00","end":"21:00"}],"tuesday":[{"start":"09:00","end":"21:00"}],"wednesday":[{"start":"09:00","end":"21:00"}],"thursday":[{"start":"09:00","end":"21:00"}],"friday":[{"start":"09:00","end":"21:00"}],"saturday":[{"start":"09:00","end":"21:00"}],"sunday":[{"start":"09:00","end":"21:00"}]}',
    '07:00',
    '20:00',
    0,
    0,
    1,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
ON CONFLICT(id) DO UPDATE SET
    owner_switch_participant_id = excluded.owner_switch_participant_id,
    allowed_room_id = excluded.allowed_room_id,
    updated_at = CURRENT_TIMESTAMP;
