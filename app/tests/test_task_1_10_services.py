import unittest
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from types import SimpleNamespace
from unittest.mock import Mock

from app.services.payout_service import close_month, payout_rows
from app.services.reports_service import yearly_listener_summary


class PayoutServiceTests(unittest.TestCase):
    def test_payout_rounds_equal_artist_share_half_up(self):
        payouts = payout_rows(
            [
                SimpleNamespace(
                    artist_id=7,
                    stream_count=1,
                    credited_streams=Decimal("0.5"),
                )
            ],
            date(2026, 10, 1),
            Decimal("0.01"),
        )

        self.assertEqual(payouts[0]["stream_count"], 1)
        self.assertEqual(payouts[0]["amount"], Decimal("0.01"))

    def test_closing_an_existing_month_rolls_back_without_writing(self):
        session = Mock()
        session.execute.return_value.first.return_value = (1,)

        with self.assertRaises(HTTPException) as error:
            close_month(session, date(2026, 10, 1), Decimal("0.01"))

        self.assertEqual(error.exception.status_code, 409)
        session.rollback.assert_called_once()
        session.commit.assert_not_called()


class ReportsServiceTests(unittest.TestCase):
    def test_yearly_summary_combines_monthly_stats_and_ranks_ties_stably(self):
        documents = [
            {
                "plays": 2,
                "streams": 1,
                "seconds": 90,
                "tracks": [
                    {
                        "track_id": 20,
                        "title": "B",
                        "streams": 1,
                        "seconds": 60,
                        "artist_ids": [2],
                        "artists": ["Artist B"],
                        "genres": ["Rock"],
                    }
                ],
                "days": [
                    {"day": "2026-01-02", "seconds": 60},
                    {"day": "2026-01-03", "seconds": 30},
                ],
            },
            {
                "plays": 1,
                "streams": 1,
                "seconds": 60,
                "tracks": [
                    {
                        "track_id": 10,
                        "title": "A",
                        "streams": 1,
                        "seconds": 60,
                        "artist_ids": [1],
                        "artists": ["Artist A"],
                        "genres": ["Pop"],
                    }
                ],
                "days": [{"day": "2026-01-02", "seconds": 60}],
            },
        ]

        report = yearly_listener_summary(documents, listener_id=5, year=2026)

        self.assertEqual(report["plays"], 3)
        self.assertEqual(report["total_minutes"], 2.5)
        self.assertEqual([item["track_id"] for item in report["top_tracks"]], [10, 20])
        self.assertEqual(report["top_genre"], "Pop")
        self.assertEqual(report["peak_day"], "2026-01-02")
        self.assertEqual(report["peak_day_seconds"], 120)

    def test_yearly_summary_returns_not_found_without_documents(self):
        with self.assertRaises(HTTPException) as error:
            yearly_listener_summary([], listener_id=5, year=2026)
        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
