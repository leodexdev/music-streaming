#!/usr/bin/env python3
"""Concurrency test, scenario 1: family plan (F3).

Fixture: a premium_family subscription with the owner and 1 member (2 members),
a valid invite code and 50 free listeners. All 50 use the code at the same moment.
Expected in real mode: exactly 4 join, 46 are refused, PostgreSQL shows 6 members.

The fixture writes straight to the database as the owner role (MIGRATION_DATABASE_URL).
Only the contested requests go through the API. It only touches rows it created
(listeners with the email prefix below), so it is safe to run after the seed.

Naive mode: the member-limit trigger would hide the race, so the fixture disables it
for the run and enables it again at the end (even if the script fails).

Exit code: 1 if the rule is broken or, in real mode, if the result is not the expected
one or any request returned 5xx. 0 otherwise. In naive mode exit 1 is expected,
because the race breaks the rule.
"""
import argparse
import asyncio
import os
import sys

import httpx
import psycopg

EMAIL_PREFIX = "ct-family-"
INVITE_CODE = "CT-FAMILY"
N_JOINERS = 50
MAX_MEMBERS = 6
EXPECTED_ACCEPTED = MAX_MEMBERS - 2  # owner + 1 member are already inside
TRIGGER = "subscription_member_limit"


def create_fixture(conn) -> dict:
    """Delete the previous fixture and create a new one. Returns the ids."""
    like = EMAIL_PREFIX + "%"
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM subscription_member WHERE listener_id IN "
        "(SELECT id FROM listener WHERE email LIKE %s)", (like,))
    cur.execute(
        "DELETE FROM subscription WHERE owner_id IN "
        "(SELECT id FROM listener WHERE email LIKE %s)", (like,))  # invite_code cascades
    cur.execute("DELETE FROM listener WHERE email LIKE %s", (like,))

    cur.execute(
        """INSERT INTO listener (display_name, email, password_hash, birth_date, country)
           SELECT 'ct' || g, %s::text || g || '@test.local', 'h', DATE '2000-01-01', 'PT'
           FROM generate_series(1, %s::int) g
           RETURNING id""",
        (EMAIL_PREFIX, N_JOINERS + 2))
    ids = sorted(row[0] for row in cur.fetchall())
    owner, member, joiners = ids[0], ids[1], ids[2:]

    cur.execute(
        """INSERT INTO subscription (owner_id, plan_id, status, started_at)
           SELECT %s::bigint, id, 'active', current_date FROM plan
           WHERE name = 'premium_family' RETURNING id""", (owner,))
    sub_id = cur.fetchone()[0]

    for listener_id in (owner, member):
        cur.execute(
            "INSERT INTO subscription_member (subscription_id, listener_id) VALUES (%s, %s)",
            (sub_id, listener_id))
    cur.execute(
        "INSERT INTO invite_code (code, subscription_id, expires_at) "
        "VALUES (%s, %s, now() + interval '7 days')", (INVITE_CODE, sub_id))
    return {"sub_id": sub_id, "joiners": joiners}


async def fire(base_url: str, mode: str, joiners: list[int]) -> list[int]:
    """Send all requests at the same moment (a gate releases them together)."""
    gate = asyncio.Event()
    limits = httpx.Limits(max_connections=len(joiners), max_keepalive_connections=len(joiners))
    async with httpx.AsyncClient(base_url=base_url, timeout=60, limits=limits) as client:

        async def one(listener_id: int) -> int:
            await gate.wait()
            try:
                response = await client.post(
                    f"/subscriptions/join?mode={mode}",
                    json={"invite_code": INVITE_CODE},
                    headers={"X-User-Id": str(listener_id)})
                return response.status_code
            except httpx.HTTPError:
                return 0  # connection error or timeout: counts as a failure

        tasks = [asyncio.create_task(one(listener_id)) for listener_id in joiners]
        await asyncio.sleep(0.5)  # let every task reach the gate
        gate.set()
        return await asyncio.gather(*tasks)


def main() -> int:
    parser = argparse.ArgumentParser(description="Family plan concurrency test (F3)")
    parser.add_argument("--mode", choices=["real", "naive"], default="real")
    parser.add_argument("--base-url", default="http://localhost:8001")
    args = parser.parse_args()

    url = os.environ.get("MIGRATION_DATABASE_URL")
    if not url:
        print("MIGRATION_DATABASE_URL is not set (owner role).", file=sys.stderr)
        return 2
    url = url.replace("postgresql+psycopg://", "postgresql://", 1)

    with psycopg.connect(url, autocommit=True) as conn:
        # a previous crashed naive run could have left the trigger disabled
        conn.execute(f"ALTER TABLE subscription_member ENABLE TRIGGER {TRIGGER}")
        fixture = create_fixture(conn)

        if args.mode == "naive":
            conn.execute(f"ALTER TABLE subscription_member DISABLE TRIGGER {TRIGGER}")
        try:
            statuses = asyncio.run(fire(args.base_url, args.mode, fixture["joiners"]))
        finally:
            conn.execute(f"ALTER TABLE subscription_member ENABLE TRIGGER {TRIGGER}")

        members = conn.execute(
            "SELECT count(*) FROM subscription_member "
            "WHERE subscription_id = %s AND left_at IS NULL", (fixture["sub_id"],)
        ).fetchone()[0]

    accepted = sum(1 for s in statuses if 200 <= s < 300)
    refused = sum(1 for s in statuses if 400 <= s < 500)
    failed = len(statuses) - accepted - refused  # 5xx and connection errors

    rule_holds = members <= MAX_MEMBERS
    print(f"Scenario: family plan (F3) | mode: {args.mode}")
    print(f"Requests: {len(statuses)} | accepted: {accepted} | refused: {refused} | 5xx/errors: {failed}")
    print(f"Members in PostgreSQL: {members} (limit {MAX_MEMBERS}) -> rule {'HOLDS' if rule_holds else 'BROKEN'}")

    ok = rule_holds
    if args.mode == "real":
        ok = ok and failed == 0 and accepted == EXPECTED_ACCEPTED and members == MAX_MEMBERS
        print(f"Expected: accepted {EXPECTED_ACCEPTED}, refused {N_JOINERS - EXPECTED_ACCEPTED}, "
              f"members {MAX_MEMBERS} -> {'OK' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())