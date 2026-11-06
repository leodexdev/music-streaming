# Project C: Music streaming

Read [README.md](README.md) first. It has the rules, requirements, documentation, Git rules and grading that apply to this project. This file describes the business.

## Context

A music streaming service lets people listen to a catalogue of tracks from labels and independent artists. Free users listen with limits, paying users without them, and families share one subscription. Every play is recorded, because artists are paid by the number of streams.

The business has two concurrency problems. A family plan has 6 places, and the invite code is often shared in a family group chat where everyone taps it at once: a seventh member gets premium for free. And collaborative playlists, edited by several friends at the same time before a party, end up with two tracks in the same position, gaps, or more tracks than the limit. Your project must make both impossible.

## Actors

- **Listener**: listens, follows artists, builds playlists, subscribes.
- **Artist and label**: publish albums and tracks and read their statistics.
- **Back office**: the company's staff, who manage plans, charge subscriptions, pay artists and read reports.

## Requirements

Everything below must be representable in your design. Names in this section are business names, not table or column names: the schema is yours to design.

### Catalogue

- A label has a name (unique) and a country. Independent artists have no label.
- An artist has a name, a country, an optional label, and a verified flag. Two artists can have the same name.
- An album has a title, a type (`album`, `single` or `ep`), a release date, a label (optional) and one or more main artists, in order.
- A track belongs to exactly one album and has a title, a position on the album (track 1, 2, ...; unique within the album), a duration in seconds (greater than 0), an explicit flag, an ISRC code (12 letters and digits, unique), and one or more genres.
- A track has one or more artists, each with a role: `main`, `featured`, `producer` or `songwriter`. The order of the main and featured artists matters ("Artist A feat. Artist B").
- Tracks have details that vary a lot and that the company wants to extend without changing the database: lyrics (with synced timestamps or not), language, BPM, key, full credits (mixing, mastering, instruments, studio), and a list of countries where the track is not available for licensing reasons.

### Listeners and plans

- A listener has a display name, an email (unique), a password hash, a date of birth, a country and the date they registered.
- There are plans: `free`, `premium_individual`, `premium_duo` (2 members) and `premium_family` (up to 6 members). Each paid plan has a monthly price in euros and a maximum number of members.
- A subscription has an owner (a listener), a paid plan, a start date, an optional end date and a status: `active`, `past_due` or `cancelled`. In this brief, a subscription is **current** when its status is `active` or `past_due`.
- A listener without a current subscription, as owner or member, is on the free plan. The free plan has no subscription.
- A listener can own at most one current subscription, and can be a member (owner included) of at most one current subscription.
- The owner of a duo or family subscription creates an invite code. Other listeners join the subscription with that code. **A subscription can never have more members, owner included, than its plan allows.**
- When the owner cancels, the subscription becomes `cancelled` and every member's membership ends on that date. Memberships are kept as history.
- Every month, the back office charges every current subscription for that month. A charge is a payment with an amount, the month it pays for, a date, a status (`approved`, `declined` or `refunded`) and a provider reference (unique). A subscription is charged at most once per month. Payments are simulated: the request carries a field `simulate` with the value `approved` or `declined`, applied to every subscription in that charge run, or a list of the subscriptions to decline. A declined charge makes the subscription `past_due`; an approved one makes it `active`.

### Listening

- Every play records the listener, the track, when it started, how many seconds were played, the device type (`mobile`, `desktop`, `web`, `speaker`, `car`) and the country.
- A play counts as a **stream** if at least 30 seconds were played. Only streams count for artist payouts and charts. A play shorter than 30 seconds is a **short play**.
- A listener can only play on **one device at a time**. Starting a track on a device makes it the active device and ends playback on any other. While playing, the active device sends a heartbeat every 30 seconds. A heartbeat or a play report from a device that is no longer active is refused with 409. The rule applies to each member of a family separately.
- A **skip** is a call to the skip endpoint: it ends the current play (with the seconds played so far) and moves to the next track. Free listeners can skip at most **6 times per hour**. The 7th skip in the same hour is refused, and the track keeps playing.
- A listener can like tracks and follow artists. Likes and follows are unique per listener and track or artist, and record when they were made.

### Playlists

- A playlist has an owner, a name, a description, a visibility (`public` or `private`), and the date it was created and last changed.
- A playlist holds an ordered list of tracks. The same track can appear more than once. The positions are 1, 2, 3, ... with **no gaps and no duplicates**.
- A playlist holds at most **500 tracks**.
- Adding a track at position *p* moves the tracks from *p* onwards one position down. *p* must be between 1 and the current number of tracks plus 1 (which appends the track); any other value is refused with 422. Removing a track moves the tracks after it one position up. Moving a track does both.
- A playlist can be **collaborative**: the owner adds collaborators, and every collaborator can add, remove and move tracks. Every change records who made it and when.

Shifting positions with `UPDATE ... SET position = position + 1` breaks a plain `UNIQUE (playlist_id, position)` constraint in the middle of the statement. Declare the constraint `DEFERRABLE INITIALLY DEFERRED` so it is checked at commit, or shift in two steps (first to negative positions, then to the final ones). See the [PostgreSQL documentation on `DEFERRABLE`](https://www.postgresql.org/docs/current/sql-createtable.html).

### Payouts

- The back office closes a month and the app computes the payouts. Each artist with the `main` role on a track receives the rate per stream of that month, set by the back office, for each stream of that track. When a track has several main artists, the amount is divided equally.
- A stream belongs to the month in which the play started, Lisbon time. Amounts are rounded to the cent, half up.
- A payout records the artist, the month, the number of streams, the amount and a status: `computed` or `paid`. An artist has at most one payout per month, so closing a month twice fails. A payout cannot be changed after it is `paid`.

## Where the rules are enforced

Must be enforced by PostgreSQL:

- A subscription never has more members than its plan allows.
- The positions of a playlist are unique, and a playlist never has more than 500 tracks.
- A listener owns at most one current subscription.
- A subscription is charged at most once per month; an artist has at most one payout per month.
- Durations are greater than 0; prices, rates and amounts are never negative.
- Unique values: label name, ISRC, track position within its album, listener email, like per listener and track, follow per listener and artist, provider reference.
- An ISRC has exactly 12 letters and digits; statuses, plan names, roles, album types and device types only take the values listed above.
- Plays are never updated or deleted by the app role.

May be enforced in PostgreSQL or in the app (say which in `docs/postgres.md`):

- A listener is a member of at most one current subscription.
- No gaps in the positions of a playlist.
- A payout cannot change after it is `paid`.
- The skip limit and the single active device (these live in Redis in most designs).

## Flows the app must implement

All flows are mandatory. F3 and F5 are the concurrent flows.

| Flow | Description |
|------|-------------|
| F1. Catalogue | Search tracks by a part of their title; show an album with its tracks and an artist with their albums. |
| F2. Subscriptions | A listener subscribes to a paid plan with a simulated first charge, or cancels. The back office runs the monthly charge for a given month. |
| F3. Join a plan | A listener joins a duo or family subscription with an invite code, with every rule in [Listeners and plans](#listeners-and-plans). |
| F4. Play | A listener starts a track on a device, sends heartbeats, reports how many seconds were played, and skips, with every rule in [Listening](#listening). |
| F5. Edit a playlist | The owner or a collaborator adds a track at a position, removes a track, or moves a track, with every rule in [Playlists](#playlists). |
| F6. Charts | The top 50 tracks by streams today, globally and per country, and a listener's last 50 tracks played. This is on the home screen of every listener. **Read from Redis**: a repeated request must not query PostgreSQL. |
| F7. Monthly payouts | The back office closes a month and the payouts are computed. |
| F8. Reports | The back office and the artists read the reports of [Reports](#reports-mongodb). |

## The concurrent flow

The rules under test are:

1. A subscription never has more members than its plan allows.
2. A playlist never has two tracks in the same position, gaps in the positions, or more than 500 tracks.
3. A listener never plays on two devices at the same time.

Project must cover at least these two scenarios:

- **Family plan** (F3). The fixture creates a `premium_family` subscription with the owner and 1 member, a valid invite code, and 50 listeners on the free plan. All 50 use the invite code at the same moment. Exactly 4 join and 46 are refused. At the end, PostgreSQL shows 6 members.
- **Collaborative playlist** (F5). The fixture creates a collaborative playlist with 490 tracks and 5 collaborators. The collaborators send 50 requests at the same moment, each adding one track at a random position between 1 and 491. Exactly 10 are added and 40 refused. At the end, the positions in PostgreSQL are exactly 1 to 500.

Covering rule 3 too is a good extension.

## MongoDB collections

Mandatory:

- **Playback events**: the raw events the apps send (start, heartbeat, pause, seek, skip, end), one document per event, with the listener, the device, the track, the position in the track and the time. Written by F4. Kept for 30 days, with a TTL index.
- **Report collections**: the derived collections written by the report export (see the README), with the data your pipelines need: for example one document per listener per month with their plays, or one per track per day. The shape is yours to design. The plays of the last 12 months come from PostgreSQL.

You decide:

- Where the track details that vary (see [Catalogue](#catalogue)) are stored: in MongoDB, in a `jsonb` column, or in tables. Justify the choice in `docs/mongodb.md`.

## Reports (MongoDB)

Your pipelines must answer at least 3 of these:

1. A yearly summary per listener ("your year in music"): minutes listened, top 5 artists, top 5 tracks, top genre, the day with most listening.
2. Streams per artist per country per month, for the artist's dashboard.
3. The top genres per country per month.
4. Short-play rate per track: the share of plays shorter than 30 seconds, for tracks with at least 1,000 plays.
5. Retention: of the listeners who registered in each month, how many played at least one track in each of the following 3 months.
6. Listening per hour of the day and per device type, per country.

## Real-time features (Redis)

- The top 50 tracks by streams today, globally and per country, updated with every stream.
- A listener's last 50 tracks played.
- The active device of each listener.
- The skip counter of free listeners, per hour.
- Stream counters per track for today, which must match the plays recorded in PostgreSQL (the verify script checks this).

## Data that expires

| Data | How long it lives | Where |
|------|-------------------|-------|
| The active device of a listener | 60 seconds after the last heartbeat | you decide |
| The skip counter of a free listener | 1 hour | you decide |
| The daily charts | the current day, Lisbon time; the previous day's charts are kept for 7 days | you decide |
| An invite code | 7 days after it is created, or until the subscription is full | you decide |
| The playback events | 30 days | MongoDB, with a TTL index |

Document each decision in `docs/architecture.md`.

## Frequent queries (PostgreSQL)

Use at least 3 of these for the `EXPLAIN` evidence required in the README:

1. The streams of a track in a given month (for payouts).
2. A listener's plays, newest first, 50 per page.
3. The tracks of a playlist in order.
4. Search tracks whose title contains a given text (think about which index can serve this; `pg_trgm` is one answer).
5. The current members of a subscription.
6. The tracks of an artist with their number of streams in the last 30 days.

## Seed volumes

| Data | Volume |
|------|--------|
| Labels | 300 |
| Artists | 20,000 |
| Albums | 60,000 |
| Tracks | 300,000 |
| Listeners | 100,000 |
| Subscriptions | about 35,000, of all paid plans, some with the maximum members |
| Monthly charges | one per month of each current or past subscription |
| Plays | at least 2,000,000, over the last 12 months |
| Playlists | 100,000 |
| Playlist entries | about 1,000,000 |
| Likes and follows | about 500,000 together |
| Playback events (MongoDB) | at least 50,000 documents, within the last 30 days |
| Report collections (MongoDB) | written by the report export from the seeded data |

About 25% of plays are short plays. Plays are spread unevenly: at least 200 tracks have 1,000 plays or more, and most tracks have very few. Some playlists are collaborative, and some have 500 tracks.

## Ideas to go further

- Offline downloads for premium listeners, with a limit of devices and tracks.
- Radio: a playlist generated from a track, avoiding tracks the listener skipped.
- Concert presale codes for the top listeners of an artist, with a limited number of codes.
- Detection of fraudulent streams: one account playing the same track 24 hours a day.
- Payout reconciliation: prove that the sum of payouts of a month matches the streams of that month.