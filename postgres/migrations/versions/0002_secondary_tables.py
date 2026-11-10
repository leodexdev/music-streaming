"""secondary tables: genre, track_genre, track_like, artist_follow, payment, payout

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-10

These tables are leaves: nothing else in the schema points to them.
Runs as music_owner, so the tables are owned by music_owner.
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


UPGRADE_STATEMENTS = [
    # ------------------------------------------------------------------ genre
    """
    CREATE TABLE genre (
        id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        name text   NOT NULL,
        CONSTRAINT uq_genre_name UNIQUE (name),
        CONSTRAINT ck_genre_name_not_blank CHECK (btrim(name) <> '')
    )
    """,
    # ------------------------------------------------------------ track_genre
    """
    CREATE TABLE track_genre (
        track_id bigint NOT NULL REFERENCES track (id) ON DELETE CASCADE,
        genre_id bigint NOT NULL REFERENCES genre (id) ON DELETE RESTRICT,
        PRIMARY KEY (track_id, genre_id)
    )
    """,
    "CREATE INDEX ix_track_genre_genre_id ON track_genre (genre_id)",
    # ------------------------------------------------------------- track_like
    """
    CREATE TABLE track_like (
        listener_id bigint      NOT NULL REFERENCES listener (id) ON DELETE CASCADE,
        track_id    bigint      NOT NULL REFERENCES track (id)    ON DELETE CASCADE,
        liked_at    timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (listener_id, track_id)
    )
    """,
    "CREATE INDEX ix_track_like_track_id ON track_like (track_id)",
    # ---------------------------------------------------------- artist_follow
    """
    CREATE TABLE artist_follow (
        listener_id bigint      NOT NULL REFERENCES listener (id) ON DELETE CASCADE,
        artist_id   bigint      NOT NULL REFERENCES artist (id)   ON DELETE CASCADE,
        followed_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (listener_id, artist_id)
    )
    """,
    "CREATE INDEX ix_artist_follow_artist_id ON artist_follow (artist_id)",
    # ---------------------------------------------------------------- payment
    # Financial record: RESTRICT, so a subscription with payments cannot be
    # deleted by accident.
    """
    CREATE TABLE payment (
        id              bigint        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        subscription_id bigint        NOT NULL REFERENCES subscription (id) ON DELETE RESTRICT,
        month           date          NOT NULL,
        amount          numeric(10,2) NOT NULL,
        paid_at         timestamptz,
        status          text          NOT NULL DEFAULT 'pending',
        provider_ref    text,
        CONSTRAINT uq_payment_provider_ref UNIQUE (provider_ref),
        CONSTRAINT ck_payment_month_first_day CHECK (EXTRACT(DAY FROM month) = 1),
        CONSTRAINT ck_payment_amount CHECK (amount >= 0),
        CONSTRAINT ck_payment_status
            CHECK (status IN ('pending', 'paid', 'failed', 'refunded')),
        CONSTRAINT ck_payment_paid_has_date
            CHECK (status <> 'paid' OR paid_at IS NOT NULL)
    )
    """,
    "CREATE INDEX ix_payment_subscription_month ON payment (subscription_id, month)",
    # at most one successful payment per subscription and month (failed
    # attempts can be retried)
    """
    CREATE UNIQUE INDEX uq_payment_one_paid_per_month
        ON payment (subscription_id, month)
        WHERE status = 'paid'
    """,
    # ----------------------------------------------------------------- payout
    """
    CREATE TABLE payout (
        id              bigint         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        artist_id       bigint         NOT NULL REFERENCES artist (id) ON DELETE RESTRICT,
        month           date           NOT NULL,
        rate_per_stream numeric(10,6)  NOT NULL,
        stream_count    integer        NOT NULL DEFAULT 0,
        amount          numeric(12,2)  NOT NULL DEFAULT 0,
        status          text           NOT NULL DEFAULT 'pending',
        CONSTRAINT uq_payout_artist_month UNIQUE (artist_id, month),
        CONSTRAINT ck_payout_month_first_day CHECK (EXTRACT(DAY FROM month) = 1),
        CONSTRAINT ck_payout_rate CHECK (rate_per_stream >= 0),
        CONSTRAINT ck_payout_stream_count CHECK (stream_count >= 0),
        CONSTRAINT ck_payout_amount CHECK (amount >= 0),
        CONSTRAINT ck_payout_status
            CHECK (status IN ('pending', 'paid', 'failed'))
    )
    """,
    # ----------------------------------------------------------------- grants
    # music_app: normal read/write. Payments and payouts cannot be deleted.
    "GRANT SELECT, INSERT, UPDATE, DELETE ON genre, track_genre, track_like, artist_follow TO music_app",
    "GRANT SELECT, INSERT, UPDATE ON payment, payout TO music_app",
    # music_ro: reports and the MongoDB export
    "GRANT SELECT ON genre, track_genre, track_like, artist_follow, payment, payout TO music_ro",
]


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    # reverse order of creation; dropping a table also drops its indexes and grants
    for table in (
        "payout",
        "payment",
        "artist_follow",
        "track_like",
        "track_genre",
        "genre",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")