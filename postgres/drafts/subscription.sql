CREATE TABLE subscription (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_id    bigint NOT NULL REFERENCES listener(id),
    plan_id     bigint NOT NULL REFERENCES plan(id),
    status      text   NOT NULL CHECK (status IN ('active','past_due','cancelled')),
    started_at  date   NOT NULL,
    ended_at    date,
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE UNIQUE INDEX subscription_one_current_per_owner
    ON subscription (owner_id) WHERE status IN ('active','past_due');

CREATE TABLE subscription_member (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subscription_id bigint NOT NULL REFERENCES subscription(id),
    listener_id     bigint NOT NULL REFERENCES listener(id),
    joined_at       timestamptz NOT NULL DEFAULT now(),
    left_at         timestamptz,
    CHECK (left_at IS NULL OR left_at >= joined_at)
);

CREATE UNIQUE INDEX member_one_current_per_listener
    ON subscription_member (listener_id) WHERE left_at IS NULL;

CREATE INDEX member_subscription_idx ON subscription_member (subscription_id);

CREATE TABLE invite_code (
    code            text PRIMARY KEY,
    subscription_id bigint NOT NULL REFERENCES subscription(id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    expires_at      timestamptz NOT NULL,
    CHECK (expires_at > created_at)
);


CREATE FUNCTION enforce_max_members() RETURNS trigger AS $$
DECLARE
    max_allowed int;
    current_count int;
BEGIN

    SELECT p.max_members INTO max_allowed
    FROM subscription s JOIN plan p ON p.id = s.plan_id
    WHERE s.id = NEW.subscription_id
    FOR UPDATE OF s;

    SELECT count(*) INTO current_count
    FROM subscription_member
    WHERE subscription_id = NEW.subscription_id AND left_at IS NULL;

    IF current_count >= max_allowed THEN
        RAISE EXCEPTION 'subscription is full' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER subscription_member_limit
    BEFORE INSERT ON subscription_member
    FOR EACH ROW EXECUTE FUNCTION enforce_max_members();