import os
import random
import string
from datetime import date, datetime, timezone
from sqlalchemy import create_engine, text
from faker import Faker
from dotenv import load_dotenv, find_dotenv

# 1. This automatically finds the .env file in the root directory
load_dotenv(find_dotenv())

# 2. We use MIGRATION_DATABASE_URL because 'music_owner' has TRUNCATE permissions.
DB_URI = os.getenv(
    "MIGRATION_DATABASE_URL", 
    "postgresql://music_owner:change-me-owner@127.0.0.1:5432/music"
)

engine = create_engine(DB_URI)
fake = Faker()

def generate_isrc():
    """Generates a valid 12-character alphanumeric ISRC."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

def seed():
    with engine.begin() as conn:
        print(f"Connecting to database as owner to clear data...")
        
        # TRUNCATE cascade clears all tables and restarts identity sequences
        conn.execute(text("""
            TRUNCATE TABLE label, artist, album, track, listener, subscription, play, 
                           playlist, genre, payment, payout RESTART IDENTITY CASCADE;
        """))

        print("Fetching plans...")
        plans = conn.execute(text("SELECT id, name, monthly_price, max_members FROM plan")).fetchall()
        plan_map = {p.name: p for p in plans}

        print("Seeding Labels & Genres...")
        labels = []
        for _ in range(5):
            res = conn.execute(text(
                "INSERT INTO label (name, country) VALUES (:name, :country) RETURNING id"
            ), {"name": fake.company() + " Records", "country": fake.country_code()})
            labels.append(res.scalar())

        genres = []
        for g_name in ["Pop", "Rock", "Hip Hop", "Jazz", "Classical", "Electronic", "R&B"]:
            res = conn.execute(text(
                "INSERT INTO genre (name) VALUES (:name) RETURNING id"
            ), {"name": g_name})
            genres.append(res.scalar())

        print("Seeding Artists...")
        artists = []
        for _ in range(20):
            res = conn.execute(text("""
                INSERT INTO artist (name, country, label_id, verified) 
                VALUES (:name, :country, :label, :verified) RETURNING id
            """), {
                "name": fake.name(), 
                "country": fake.country_code(), 
                "label": random.choice(labels), 
                "verified": random.choice([True, False])
            })
            artists.append(res.scalar())

        print("Seeding Albums and Tracks...")
        tracks = []
        for _ in range(30):
            # Create Album
            album_type = random.choice(["album", "single", "ep"])
            album_res = conn.execute(text("""
                INSERT INTO album (title, type, release_date, label_id) 
                VALUES (:title, :type, :date, :label) RETURNING id
            """), {
                "title": fake.catch_phrase(),
                "type": album_type,
                "date": fake.date_between(start_date="-5y", end_date="today"),
                "label": random.choice(labels)
            })
            album_id = album_res.scalar()

            # Assign Artists to Album
            album_artists = random.sample(artists, k=random.randint(1, 2))
            for pos, art_id in enumerate(album_artists, start=1):
                conn.execute(text("""
                    INSERT INTO album_artist (album_id, artist_id, position) 
                    VALUES (:alb, :art, :pos)
                """), {"alb": album_id, "art": art_id, "pos": pos})

            # Create Tracks for Album
            num_tracks = random.randint(1, 3) if album_type == "single" else random.randint(4, 12)
            for track_pos in range(1, num_tracks + 1):
                track_res = conn.execute(text("""
                    INSERT INTO track (album_id, title, position, duration_seconds, explicit, isrc)
                    VALUES (:alb, :title, :pos, :dur, :exp, :isrc) RETURNING id
                """), {
                    "alb": album_id,
                    "title": fake.sentence(nb_words=3).replace(".", ""),
                    "pos": track_pos,
                    "dur": random.randint(120, 300),
                    "exp": random.choice([True, False]),
                    "isrc": generate_isrc()
                })
                track_id = track_res.scalar()
                tracks.append(track_id)

                # Assign Track Artists
                for art_pos, art_id in enumerate(album_artists, start=1):
                    conn.execute(text("""
                        INSERT INTO track_artist (track_id, artist_id, role, position)
                        VALUES (:trk, :art, 'main', :pos)
                    """), {"trk": track_id, "art": art_id, "pos": art_pos})
                
                # Assign Genre
                conn.execute(text("INSERT INTO track_genre (track_id, genre_id) VALUES (:t, :g)"), 
                             {"t": track_id, "g": random.choice(genres)})

        print("Seeding Listeners & Subscriptions...")
        listeners = []
        for _ in range(50):
            res = conn.execute(text("""
                INSERT INTO listener (display_name, email, password_hash, birth_date, country)
                VALUES (:name, :email, :pass, :birth, :country) RETURNING id
            """), {
                "name": fake.user_name(),
                "email": fake.unique.email(),
                "pass": "pbkdf2:sha256:...", # Dummy hash
                "birth": fake.date_of_birth(minimum_age=13, maximum_age=65),
                "country": fake.country_code()
            })
            listener_id = res.scalar()
            listeners.append(listener_id)

            # 60% chance to have an active subscription as an owner
            if random.random() < 0.6:
                plan = random.choice(list(plan_map.values()))
                start_date = fake.date_between(start_date="-1y", end_date="today")
                sub_res = conn.execute(text("""
                    INSERT INTO subscription (owner_id, plan_id, status, started_at)
                    VALUES (:owner, :plan, 'active', :start) RETURNING id
                """), {"owner": listener_id, "plan": plan.id, "start": start_date})
                sub_id = sub_res.scalar()

                # Add owner as the first member
                conn.execute(text("""
                    INSERT INTO subscription_member (subscription_id, listener_id, joined_at)
                    VALUES (:sub, :lis, :joined)
                """), {"sub": sub_id, "lis": listener_id, "joined": datetime.combine(start_date, datetime.min.time())})

                # Generate a payment (must be 1st of the month per your CHECK constraint)
                pay_month = start_date.replace(day=1)
                conn.execute(text("""
                    INSERT INTO payment (subscription_id, month, amount, paid_at, status, provider_ref)
                    VALUES (:sub, :month, :amount, :paid, 'approved', :ref)
                """), {
                    "sub": sub_id,
                    "month": pay_month,
                    "amount": plan.monthly_price,
                    "paid": datetime.now(timezone.utc),
                    "ref": f"stripe_{fake.unique.hexify(text='^^^^^^^^')}"
                })

        print("Seeding Plays & Likes...")
        for _ in range(300):
            conn.execute(text("""
                INSERT INTO play (listener_id, track_id, started_at, seconds_played, device_type, country)
                VALUES (:lis, :trk, :start, :sec, :dev, :country)
            """), {
                "lis": random.choice(listeners),
                "trk": random.choice(tracks),
                "start": fake.date_time_between(start_date="-30d", end_date="now", tzinfo=timezone.utc),
                "sec": random.randint(10, 300),
                "dev": random.choice(["mobile", "desktop", "web", "speaker", "car"]),
                "country": fake.country_code()
            })

            # Randomly like a track (try/except skips if already liked due to composite PK)
            try:
                with conn.begin_nested(): # use a savepoint so a failure doesn't rollback the whole transaction
                    conn.execute(text("INSERT INTO track_like (listener_id, track_id) VALUES (:l, :t)"), 
                                 {"l": random.choice(listeners), "t": random.choice(tracks)})
            except:
                pass

        print("Seeding Playlists...")
        for _ in range(15):
            owner_id = random.choice(listeners)
            pl_res = conn.execute(text("""
                INSERT INTO playlist (owner_id, name, visibility) 
                VALUES (:owner, :name, 'public') RETURNING id
            """), {"owner": owner_id, "name": fake.word().capitalize() + " Vibes"})
            pl_id = pl_res.scalar()

            # Add tracks to playlist
            pl_tracks = random.sample(tracks, k=random.randint(3, 10))
            for pos, trk_id in enumerate(pl_tracks, start=1):
                conn.execute(text("""
                    INSERT INTO playlist_track (playlist_id, position, track_id, added_by)
                    VALUES (:pl, :pos, :trk, :added)
                """), {"pl": pl_id, "pos": pos, "trk": trk_id, "added": owner_id})

        print("Seeding Payouts...")
        for artist_id in random.sample(artists, k=5):
            # Ensure day=1 to satisfy CHECK constraint
            payout_month = date.today().replace(day=1)
            conn.execute(text("""
                INSERT INTO payout (artist_id, month, rate_per_stream, stream_count, amount, status)
                VALUES (:art, :month, 0.004, 10000, 40.00, 'computed')
            """), {"art": artist_id, "month": payout_month})

    print("Seed complete! 🌱")

if __name__ == "__main__":
    seed()