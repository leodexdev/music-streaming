"""playlist change log"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "playlist_change",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("playlist_id", sa.BigInteger, sa.ForeignKey("playlist.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.BigInteger, sa.ForeignKey("listener.id", ondelete="SET NULL")),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("track_id", sa.BigInteger, sa.ForeignKey("track.id", ondelete="SET NULL")),
        sa.Column("position", sa.Integer),
        sa.Column("new_position", sa.Integer),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("action IN ('add','remove','move')", name="playlist_change_action_ck"),
    )
    op.create_index("playlist_change_playlist_idx", "playlist_change", ["playlist_id", "changed_at"])


def downgrade():
    op.drop_table("playlist_change")