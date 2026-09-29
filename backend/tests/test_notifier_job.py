from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from backend.models import Subscription
from backend.notifier import job


@dataclass
class _Sub:
    id: str
    email: str


@dataclass
class _Doc:
    id: str


def _run(subs, matches_by_sub, send_side_effect=None):
    """Run run_notification_job with a fake DB session and stubbed
    find_unsent_matches / send_announcement_email. Returns (result, db, send_email_mock)
    for inspection."""
    db = MagicMock()
    db.query.return_value.filter_by.return_value.all.return_value = subs

    session_ctx = MagicMock()
    session_ctx.__enter__.return_value = db

    with (
        patch.object(job, "SessionLocal", return_value=session_ctx),
        patch.object(job, "find_unsent_matches", side_effect=lambda _db, sub: matches_by_sub.get(sub.id, [])),
        patch.object(job, "send_announcement_email", side_effect=send_side_effect) as send_email,
    ):
        result = job.run_notification_job()

    return result, db, send_email


def _added(db):
    """(subscription_id, document_id) pairs the job wrote to sent_notifications."""
    return sorted(
        (row.subscription_id, row.document_id)
        for (row,), _ in db.add.call_args_list
    )


def test_only_confirmed_subscriptions_are_processed():
    result, db, send_email = _run(subs=[], matches_by_sub={})

    db.query.assert_called_once_with(Subscription)
    db.query.return_value.filter_by.assert_called_once_with(confirmed=True)
    assert result == 0
    send_email.assert_not_called()


def test_happy_path_emails_and_records_every_match():
    subs = [_Sub("s1", "a@example.com"), _Sub("s2", "b@example.com")]
    matches = {"s1": [_Doc("d1"), _Doc("d2")], "s2": [_Doc("d3")]}

    result, db, send_email = _run(subs, matches)

    assert result == 3
    assert send_email.call_count == 2
    send_email.assert_any_call("a@example.com", matches["s1"])
    send_email.assert_any_call("b@example.com", matches["s2"])
    assert _added(db) == [("s1", "d1"), ("s1", "d2"), ("s2", "d3")]
    db.commit.assert_called_once()


def test_subscription_with_no_matches_is_skipped_entirely():
    subs = [_Sub("s1", "a@example.com"), _Sub("s2", "b@example.com")]
    matches = {"s1": [_Doc("d1")]}  # s2 has none

    result, db, send_email = _run(subs, matches)

    assert result == 1
    send_email.assert_called_once_with("a@example.com", matches["s1"])
    assert _added(db) == [("s1", "d1")]


def test_a_failing_email_does_not_block_other_subscriptions_or_record_that_send():
    subs = [_Sub("s1", "boom@example.com"), _Sub("s2", "ok@example.com")]
    matches = {"s1": [_Doc("d1")], "s2": [_Doc("d2")]}

    def send(to, docs):
        if to == "boom@example.com":
            raise RuntimeError("smtp down")

    result, db, send_email = _run(subs, matches, send_side_effect=send)

    # s1's failed send is not counted and not written; s2 still goes through.
    assert result == 1
    assert _added(db) == [("s2", "d2")]
    db.commit.assert_called_once()
