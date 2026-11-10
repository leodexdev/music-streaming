"""primary schema"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

BIG = sa.BigInteger
TS = sa.DateTime(timezone=True)


def pk():
    return sa.Column("id", BIG, sa.Identity(), primary_key=True)


def upgrade():
    op.create_table(
        "label", pk(),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("country", sa.Text, nullable=False),
    )

    op.create_table(
        "artist", pk(),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("country", sa.Text, nullable=False),
        sa.Column("label_id", BIG, sa.ForeignKey("label.id", ondelete="SET NULL")),
        sa.Column("verified", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("artist_label_idx", "artist", ["label_id"])

    op.create_table(
        "album", pk(),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("release_date", sa.Date, nullable=False),
        sa.Column("label_id", BIG, sa.ForeignKey("label.id", ondelete="SET NULL")),
        sa.CheckConstraint("type IN ('album','single','ep')", name="album_type_ck"),
    )

    op.create_table(
        "album_artist",
        sa.Column("album_id", BIG, sa.ForeignKey("album.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("artist_id", BIG, sa.ForeignKey("artist.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("position", sa.SmallInteger, nullable=False),
        sa.CheckConstraint("position >= 1", name="album_artist_pos_ck"),
        sa.UniqueConstraint("album_id", "position", name="album_artist_pos_uq"),
    )
    op.create_index("album_artist_artist_idx", "album_artist", ["artist_id"])

    op.create_table(
        "track", pk(),
        sa.Column("album_id", BIG, sa.ForeignKey("album.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("position", sa.SmallInteger, nullable=False),
        sa.Column("duration_seconds", sa.Integer, nullable=False),
        sa.Column("explicit", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("isrc", sa.Text, nullable=False, unique=True),
        sa.CheckConstraint("position >= 1", name="track_position_ck"),
        sa.CheckConstraint("duration_seconds > 0", name="track_duration_ck"),
        sa.CheckConstraint("isrc ~ '^[A-Za-z0-9]{12}$'", name="track_isrc_ck"),
        sa.UniqueConstraint("album_id", "position", name="track_album_position_uq"),
    )

    op.create_table(
        "track_artist",
        sa.Column("track_id", BIG, sa.ForeignKey("track.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("artist_id", BIG, sa.ForeignKey("artist.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("role", sa.Text, primary_key=True),
        sa.Column("position", sa.SmallInteger, nullable=False, server_default="1"),
        sa.CheckConstraint("role IN ('main','featured','producer','songwriter')", name="track_artist_role_ck"),
        sa.CheckConstraint("position >= 1", name="track_artist_pos_ck"),
        sa.UniqueConstraint("track_id", "role", "position", name="track_artist_order_uq"),
    )
    op.create_index("track_artist_artist_idx", "track_artist", ["artist_id"])

    op.create_table(
        "listener", pk(),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("birth_date", sa.Date, nullable=False),
        sa.Column("country", sa.Text, nullable=False),
        sa.Column("registered_at", sa.Date, nullable=False, server_default=sa.text("current_date")),
    )

    plan = op.create_table(
        "plan", pk(),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("monthly_price", sa.Numeric(8, 2), nullable=False),
        sa.Column("max_members", sa.SmallInteger, nullable=False),
        sa.CheckConstraint(
            "name IN ('free','premium_individual','premium_duo','premium_family')",
            name="plan_name_ck"),
        sa.CheckConstraint("monthly_price >= 0", name="plan_price_ck"),
        sa.CheckConstraint("max_members >= 1", name="plan_members_ck"),
    )
    op.bulk_insert(plan, [
        {"name": "free", "monthly_price": 0, "max_members": 1},
        {"name": "premium_individual", "monthly_price": 9.99, "max_members": 1},
        {"name": "premium_duo", "monthly_price": 13.99, "max_members": 2},
        {"name": "premium_family", "monthly_price": 17.99, "max_members": 6},
    ])

    op.create_table(
        "subscription", pk(),
        sa.Column("owner_id", BIG, sa.ForeignKey("listener.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan_id", BIG, sa.ForeignKey("plan.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("started_at", sa.Date, nullable=False),
        sa.Column("ended_at", sa.Date),
        sa.CheckConstraint("status IN ('active','past_due','cancelled')", name="subscription_status_ck"),
        sa.CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="subscription_dates_ck"),
    )
    op.create_index("subscription_one_current_per_owner", "subscription", ["owner_id"],
                    unique=True, postgresql_where=sa.text("status IN ('active','past_due')"))

    op.create_table(
        "subscription_member", pk(),
        sa.Column("subscription_id", BIG, sa.ForeignKey("subscription.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("listener_id", BIG, sa.ForeignKey("listener.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("joined_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.Column("left_at", TS),
        sa.CheckConstraint("left_at IS NULL OR left_at >= joined_at", name="member_dates_ck"),
    )
    op.create_index("member_one_current_per_listener", "subscription_member", ["listener_id"],
                    unique=True, postgresql_where=sa.text("left_at IS NULL"))
    op.create_index("member_subscription_idx", "subscription_member", ["subscription_id"])

    op.create_table(
        "invite_code",
        sa.Column("code", sa.Text, primary_key=True),
        sa.Column("subscription_id", BIG, sa.ForeignKey("subscription.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", TS, nullable=False),
        sa.CheckConstraint("expires_at > created_at", name="invite_expiry_ck"),
    )
    op.create_index("invite_subscription_idx", "invite_code", ["subscription_id"])

    op.create_table(
        "play", pk(),
        sa.Column("listener_id", BIG, sa.ForeignKey("listener.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("track_id", BIG, sa.ForeignKey("track.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("seconds_played", sa.Integer, nullable=False),
        sa.Column("device_type", sa.Text, nullable=False),
        sa.Column("country", sa.Text, nullable=False),
        sa.CheckConstraint("seconds_played >= 0", name="play_seconds_ck"),
        sa.CheckConstraint("device_type IN ('mobile','desktop','web','speaker','car')", name="play_device_ck"),
    )

    op.create_table(
        "playlist", pk(),
        sa.Column("owner_id", BIG, sa.ForeignKey("listener.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("visibility", sa.Text, nullable=False, server_default="private"),
        sa.Column("is_collaborative", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("track_count", sa.Integer, nullable=False, server_default="0"),  # desnormalização deliberada
        sa.Column("created_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("visibility IN ('public','private')", name="playlist_visibility_ck"),
        sa.CheckConstraint("track_count BETWEEN 0 AND 500", name="playlist_max_tracks_ck"),
    )
    op.create_index("playlist_owner_idx", "playlist", ["owner_id"])

    op.create_table(
        "playlist_collaborator",
        sa.Column("playlist_id", BIG, sa.ForeignKey("playlist.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("listener_id", BIG, sa.ForeignKey("listener.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("added_at", TS, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("playlist_collab_listener_idx", "playlist_collaborator", ["listener_id"])

    op.create_table(
        "playlist_track", pk(),
        sa.Column("playlist_id", BIG, sa.ForeignKey("playlist.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("track_id", BIG, sa.ForeignKey("track.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("added_by", BIG, sa.ForeignKey("listener.id", ondelete="SET NULL")),
        sa.Column("added_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("position BETWEEN 1 AND 500", name="playlist_track_pos_ck"),
        sa.UniqueConstraint("playlist_id", "position", name="playlist_track_pos_uq",
                            deferrable=True, initially="DEFERRED"),
    )
    op.create_index("playlist_track_track_idx", "playlist_track", ["track_id"])

    # --- trigger: limite de membros (serializa com FOR UPDATE na subscrição)
    op.execute("""
    CREATE FUNCTION enforce_max_members() RETURNS trigger AS $$
    DECLARE max_allowed int; current_count int;
    BEGIN
        SELECT p.max_members INTO max_allowed
        FROM subscription s JOIN plan p ON p.id = s.plan_id
        WHERE s.id = NEW.subscription_id
        FOR UPDATE OF s;

        SELECT count(*) INTO current_count FROM subscription_member
        WHERE subscription_id = NEW.subscription_id AND left_at IS NULL;

        IF current_count >= max_allowed THEN
            RAISE EXCEPTION 'subscription is full' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    CREATE TRIGGER subscription_member_limit BEFORE INSERT ON subscription_member
    FOR EACH ROW EXECUTE FUNCTION enforce_max_members();
    """)

    # --- triggers: mantêm playlist.track_count; o CHECK <= 500 faz o resto
    op.execute("""
    CREATE FUNCTION playlist_track_count_ins() RETURNS trigger AS $$
    BEGIN
        UPDATE playlist p SET track_count = p.track_count + n.c
        FROM (SELECT playlist_id, count(*) c FROM new_rows GROUP BY playlist_id) n
        WHERE p.id = n.playlist_id;
        RETURN NULL;
    END $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    CREATE FUNCTION playlist_track_count_del() RETURNS trigger AS $$
    BEGIN
        UPDATE playlist p SET track_count = p.track_count - n.c
        FROM (SELECT playlist_id, count(*) c FROM old_rows GROUP BY playlist_id) n
        WHERE p.id = n.playlist_id;
        RETURN NULL;
    END $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    CREATE TRIGGER playlist_track_after_ins AFTER INSERT ON playlist_track
    REFERENCING NEW TABLE AS new_rows FOR EACH STATEMENT
    EXECUTE FUNCTION playlist_track_count_ins();
    """)
    op.execute("""
    CREATE TRIGGER playlist_track_after_del AFTER DELETE ON playlist_track
    REFERENCING OLD TABLE AS old_rows FOR EACH STATEMENT
    EXECUTE FUNCTION playlist_track_count_del();
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS playlist_track_after_del ON playlist_track")
    op.execute("DROP TRIGGER IF EXISTS playlist_track_after_ins ON playlist_track")
    op.execute("DROP FUNCTION IF EXISTS playlist_track_count_del()")
    op.execute("DROP FUNCTION IF EXISTS playlist_track_count_ins()")
    op.execute("DROP TRIGGER IF EXISTS subscription_member_limit ON subscription_member")
    op.execute("DROP FUNCTION IF EXISTS enforce_max_members()")
    for t in ["playlist_track", "playlist_collaborator", "playlist", "play", "invite_code",
              "subscription_member", "subscription", "plan", "listener", "track_artist",
              "track", "album_artist", "album", "artist", "label"]:
        op.drop_table(t)