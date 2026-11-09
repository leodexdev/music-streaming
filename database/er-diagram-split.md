# ER diagram: primary and secondary tables

**Rule used for the split:** primary tables are the ones the rest of the schema depends on, plus the two concurrent flows. Secondary tables are "leaves": nothing else points to them, so they can be added in later migrations.

## Primary tables (13)

```mermaid
erDiagram
    label ||--o{ artist : "signs"
    label |o--o{ album : "releases"
    album ||--|{ track : "contains"
    track ||--|{ track_artist : "credits"
    artist ||--o{ track_artist : "appears in"

    plan ||--o{ subscription : "defines"
    listener ||--o{ subscription : "owns"
    subscription ||--|{ subscription_member : "has"
    listener ||--o{ subscription_member : "belongs to"

    listener ||--o{ play : "makes"
    track ||--o{ play : "is played in"

    listener ||--o{ playlist : "owns"
    playlist ||--o{ playlist_collaborator : "has"
    listener ||--o{ playlist_collaborator : "collaborates"
    playlist ||--o{ playlist_track : "holds"
    track ||--o{ playlist_track : "is in"

    label {
        bigint id PK
        text name UK
        text country
    }
    artist {
        bigint id PK
        text name
        text country
        bigint label_id FK
        boolean verified
    }
    album {
        bigint id PK
        text title
        text type
        date release_date
        bigint label_id FK
    }
    track {
        bigint id PK
        bigint album_id FK
        text title
        int position
        int duration_seconds
        boolean explicit
        text isrc UK
    }
    track_artist {
        bigint track_id PK, FK
        bigint artist_id PK, FK
        text role PK
        int position
    }
    listener {
        bigint id PK
        text display_name
        text email UK
        text password_hash
        date birth_date
        text country
        date registered_at
    }
    plan {
        text name PK
        numeric monthly_price
        int max_members
    }
    subscription {
        bigint id PK
        bigint owner_id FK
        text plan_name FK
        date start_date
        date end_date
        text status
    }
    subscription_member {
        bigint id PK
        bigint subscription_id FK
        bigint listener_id FK
        date joined_at
        date left_at
    }
    play {
        bigint id PK
        bigint listener_id FK
        bigint track_id FK
        timestamptz started_at
        int seconds_played
        text device_type
        text country
    }
    playlist {
        bigint id PK
        bigint owner_id FK
        text name
        text description
        text visibility
        boolean is_collaborative
        timestamptz created_at
        timestamptz updated_at
    }
    playlist_collaborator {
        bigint playlist_id PK, FK
        bigint listener_id PK, FK
        timestamptz added_at
    }
    playlist_track {
        bigint id PK
        bigint playlist_id FK
        int position
        bigint track_id FK
        bigint added_by FK
        timestamptz added_at
    }
```

## Secondary tables (6)

The boxes with only `id` are primary tables, shown just so the links are visible.

```mermaid
erDiagram
    track ||--|{ track_genre : "has"
    genre ||--o{ track_genre : "tags"

    listener ||--o{ track_like : "likes"
    track ||--o{ track_like : "is liked in"
    listener ||--o{ artist_follow : "follows"
    artist ||--o{ artist_follow : "is followed in"

    subscription ||--o{ payment : "is charged by"
    artist ||--o{ payout : "receives"

    track {
        bigint id PK
    }
    listener {
        bigint id PK
    }
    artist {
        bigint id PK
    }
    subscription {
        bigint id PK
    }
    genre {
        bigint id PK
        text name UK
    }
    track_genre {
        bigint track_id PK, FK
        bigint genre_id PK, FK
    }
    track_like {
        bigint listener_id PK, FK
        bigint track_id PK, FK
        timestamptz liked_at
    }
    artist_follow {
        bigint listener_id PK, FK
        bigint artist_id PK, FK
        timestamptz followed_at
    }
    payment {
        bigint id PK
        bigint subscription_id FK
        date month
        numeric amount
        timestamptz paid_at
        text status
        text provider_ref UK
    }
    payout {
        bigint id PK
        bigint artist_id FK
        date month
        numeric rate_per_stream
        int stream_count
        numeric amount
        text status
    }
```

## Suggested migration order

1. **Migration 1 (primary):** `label`, `artist`, `album`, `track`, `track_artist`, `listener`, `plan`, `subscription`, `subscription_member`, `play`, `playlist`, `playlist_collaborator`, `playlist_track`.
2. **Migration 2 (secondary):** `genre`, `track_genre`, `track_like`, `artist_follow`, `payment`, `payout`.