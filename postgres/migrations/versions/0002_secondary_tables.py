"""secondary schema"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

BIG = sa.BigInteger
TS = sa.DateTime(timezone=True)


def pk():
    return sa.Column("id", BIG, sa.Identity(), primary_key=True)


def upgrade():
    op.create_table(
        "genre", pk(),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.CheckConstraint("btrim(name) <> ''", name="genre_name_ck"),
    )

    op.create_table(
        "track_genre",
        sa.Column("track_id", BIG, sa.ForeignKey("track.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("genre_id", BIG, sa.ForeignKey("genre.id", ondelete="RESTRICT"), primary_key=True),
    )
    op.create_index("track_genre_genre_idx", "track_genre", ["genre_id"])

    op.create_table(
        "track_like",
        sa.Column("listener_id", BIG, sa.ForeignKey("listener.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("track_id", BIG, sa.ForeignKey("track.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("liked_at", TS, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("track_like_track_idx", "track_like", ["track_id"])

    op.create_table(
        "artist_follow",
        sa.Column("listener_id", BIG, sa.ForeignKey("listener.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("artist_id", BIG, sa.ForeignKey("artist.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("followed_at", TS, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("artist_follow_artist_idx", "artist_follow", ["artist_id"])

    # financial records: RESTRICT, so a subscription or artist with money
    # records cannot be deleted by accident
    op.create_table(
        "payment", pk(),
        sa.Column("subscription_id", BIG, sa.ForeignKey("subscription.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("month", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("paid_at", TS),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("provider_ref", sa.Text, unique=True),
        sa.CheckConstraint("EXTRACT(DAY FROM month) = 1", name="payment_month_ck"),
        sa.CheckConstraint("amount >= 0", name="payment_amount_ck"),
        sa.CheckConstraint("status IN ('pending','paid','failed','refunded')", name="payment_status_ck"),
        sa.CheckConstraint("status <> 'paid' OR paid_at IS NOT NULL", name="payment_paid_at_ck"),
        sa.UniqueConstraint("subscription_id", "month", name="payment_subscription_month_uq"),
    )
    op.create_index("payment_subscription_month_idx", "payment", ["subscription_id", "month"])

    op.create_table(
        "payout", pk(),
        sa.Column("artist_id", BIG, sa.ForeignKey("artist.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("month", sa.Date, nullable=False),
        sa.Column("rate_per_stream", sa.Numeric(10, 6), nullable=False),
        sa.Column("stream_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.CheckConstraint("EXTRACT(DAY FROM month) = 1", name="payout_month_ck"),
        sa.CheckConstraint("rate_per_stream >= 0", name="payout_rate_ck"),
        sa.CheckConstraint("stream_count >= 0", name="payout_stream_count_ck"),
        sa.CheckConstraint("amount >= 0", name="payout_amount_ck"),
        sa.CheckConstraint("status IN ('pending','paid','failed')", name="payout_status_ck"),
        sa.UniqueConstraint("artist_id", "month", name="payout_artist_month_uq"),
    )

    # --- trigger: a paid payout cannot be changed
    op.execute("""
    CREATE FUNCTION prevent_paid_payout_changes() RETURNS trigger AS $$
    BEGIN
        IF OLD.status = 'paid' THEN
            RAISE EXCEPTION 'a paid payout cannot be changed'
                USING ERRCODE = '23514';
        END IF;

        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;

        RETURN NEW;
    END $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE TRIGGER payout_paid_immutable
    BEFORE UPDATE OR DELETE ON payout
    FOR EACH ROW EXECUTE FUNCTION prevent_paid_payout_changes();
    """)

    # --- grants: app reads and writes secondary tables
    op.execute("""
    GRANT SELECT, INSERT, UPDATE, DELETE
    ON genre, track_genre, track_like, artist_follow, payment, payout
    TO music_app
    """)

    # --- play: app can only read and insert
    op.execute("GRANT SELECT, INSERT ON play TO music_app")
    op.execute("REVOKE UPDATE, DELETE ON play FROM music_app")

    # --- read-only role
    op.execute("""
        GRANT SELECT
        ON genre, track_genre, track_like, artist_follow, payment, payout, play
        TO music_ro;
    """)

    # --- default privileges for future tables
    op.execute("""
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO music_app
    """)

    op.execute("""
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO music_ro
    """)

    op.execute("""
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO music_app
    """)

    op.execute("""
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO music_app
    """)


def downgrade():
    # --- remove payout trigger and function
    op.execute("DROP TRIGGER IF EXISTS payout_paid_immutable ON payout")
    op.execute("DROP FUNCTION IF EXISTS prevent_paid_payout_changes()")

    # --- revoke permissions on play
    op.execute("REVOKE SELECT, INSERT ON play FROM music_app")
    op.execute("REVOKE SELECT ON play FROM music_ro")

    # --- revoke permissions on secondary tables
    op.execute("""
    REVOKE SELECT, INSERT, UPDATE, DELETE
    ON genre, track_genre, track_like, artist_follow, payment, payout
    FROM music_app
    """)

    op.execute("""
    REVOKE SELECT
    ON genre, track_genre, track_like, artist_follow, payment, payout
    FROM music_ro
    """)

    # --- remove default privileges
    op.execute("""
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM music_app
    """)

    op.execute("""
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE SELECT ON TABLES FROM music_ro
    """)

    # --- revoke sequence permissions
    op.execute("""
    REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public FROM music_app
    """)
    
    op.execute("""
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE USAGE, SELECT ON SEQUENCES FROM music_app
    """)


    # --- drop tables in reverse order
    for t in ["payout", "payment", "artist_follow", "track_like", "track_genre", "genre"]:
        op.drop_table(t)