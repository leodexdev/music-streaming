"""grant the application role access to core project tables"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

READ_TABLES = (
    "label",
    "artist",
    "album",
    "album_artist",
    "track",
    "track_artist",
    "listener",
    "plan",
)

WRITABLE_TABLES = (
    "subscription",
    "subscription_member",
    "invite_code",
    "playlist",
    "playlist_collaborator",
    "playlist_track",
)


def upgrade():
    op.execute(
        sa.text(f"GRANT SELECT ON {', '.join(READ_TABLES)} TO music_app")
    )
    op.execute(
        sa.text(
            "GRANT SELECT, INSERT, UPDATE, DELETE "
            f"ON {', '.join(WRITABLE_TABLES)} TO music_app"
        )
    )


def downgrade():
    op.execute(
        sa.text(
            "REVOKE SELECT, INSERT, UPDATE, DELETE "
            f"ON {', '.join(WRITABLE_TABLES)} FROM music_app"
        )
    )
    op.execute(
        sa.text(f"REVOKE SELECT ON {', '.join(READ_TABLES)} FROM music_app")
    )
