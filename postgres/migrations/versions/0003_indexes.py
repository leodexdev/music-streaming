from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "play_listener_started_desc_idx", 
        "play", 
        ["listener_id", sa.text("started_at DESC")]
    )

    op.create_index(
        "play_track_started_idx", 
        "play", 
        ["track_id", "started_at"]
    )

    op.create_index(
        "track_title_trgm_idx", 
        "track", 
        ["title"], 
        postgresql_using="gin", 
        postgresql_ops={"title": "gin_trgm_ops"}
    )


def downgrade():
    op.drop_index("track_title_trgm_idx", table_name="track", if_exists=True)
    op.drop_index("play_track_started_idx", table_name="play", if_exists=True)
    op.drop_index("play_listener_started_desc_idx", table_name="play", if_exists=True)