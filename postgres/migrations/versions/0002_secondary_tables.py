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
    )
    op.create_index("payment_subscription_month_idx", "payment", ["subscription_id", "month"])
    # one successful payment per subscription and month (failed ones can be retried)
    op.create_index("payment_one_paid_per_month", "payment", ["subscription_id", "month"],
                    unique=True, postgresql_where=sa.text("status = 'paid'"))

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

    # --- grants: app reads and writes, read-only role only reads.
    # Payments and payouts cannot be deleted by the app.
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON genre, track_genre, track_like, artist_follow TO music_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON payment, payout TO music_app")
    op.execute("GRANT SELECT ON genre, track_genre, track_like, artist_follow, payment, payout TO music_ro")


def downgrade():
    # reverse order; dropping a table also drops its indexes and grants
    for t in ["payout", "payment", "artist_follow", "track_like", "track_genre", "genre"]:
        op.drop_table(t)