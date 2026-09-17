from contextlib import contextmanager
from datetime import date, time
from uuid import UUID, uuid4

from app.schemas.matching_workspace import MatchingProfileUpdate
from app.services import matching_workspace_service


class FakeCursor:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.current = None
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.executed.append((query, params))
        self.current = next(self.responses)

    def fetchone(self):
        return self.current

    def fetchall(self):
        return self.current


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor

    def cursor(self):
        return self.fake_cursor


def install_fake_connection(monkeypatch, responses):
    cursor = FakeCursor(responses)

    @contextmanager
    def fake_get_connection():
        yield FakeConnection(cursor)

    monkeypatch.setattr(
        matching_workspace_service,
        "get_connection",
        fake_get_connection,
    )
    return cursor


def test_matching_queue_selects_only_safe_matching_fields(monkeypatch):
    trip_id = uuid4()
    elderly_id = uuid4()
    cursor = install_fake_connection(
        monkeypatch,
        [
            [
                {
                    "trip_id": trip_id,
                    "elderly_id": elderly_id,
                    "elderly_name": "Mdm Lim Siew Hoon",
                    "appt_date": date(2026, 9, 8),
                    "appt_time": time(10, 0),
                    "destination": "Jurong Community Hospital",
                    "dialect": "Hokkien",
                    "weight_kg": 62.5,
                    "gender_preference": "F",
                    "wheelchair_required": True,
                }
            ]
        ],
    )

    queue = matching_workspace_service.get_matching_queue()

    assert queue[0].trip_id == trip_id
    assert "nric" not in queue[0].model_dump()
    assert "contact_no" not in queue[0].model_dump()
    query = " ".join(cursor.executed[0][0].split()).casefold()
    assert "trips.status = 'accepted'" in query
    assert "elderly_clients.escort_required = true" in query


def test_matching_profile_update_is_limited_to_matching_fields(monkeypatch):
    elderly_id = uuid4()
    cursor = install_fake_connection(
        monkeypatch,
        [
            {
                "elderly_id": elderly_id,
                "dialect": "Hokkien",
                "weight_kg": 62.5,
                "gender_preference": "F",
            }
        ],
    )

    profile = matching_workspace_service.update_matching_profile(
        elderly_id,
        MatchingProfileUpdate(
            dialect="Hokkien",
            weight_kg=62.5,
            gender_preference="F",
        ),
    )

    assert profile.elderly_id == elderly_id
    query = " ".join(cursor.executed[0][0].split()).casefold()
    assert "dialect = %s" in query
    assert "weight_kg = %s" in query
    assert "gender_preference = %s" in query
    assert "nric" not in query


def test_escort_options_explain_every_hard_filter_issue(monkeypatch):
    trip_id = uuid4()
    escort_id = uuid4()
    install_fake_connection(
        monkeypatch,
        [
            {
                "escort_id": None,
                "appt_date": date(2026, 9, 8),
                "appt_time": time(10, 0),
                "status": "accepted",
                "wheelchair_required": True,
            },
            [
                {
                    "id": escort_id,
                    "name": "Mei Ling",
                    "gender": "F",
                    "dialects": ["Hokkien"],
                    "available_days": ["Mon"],
                    "available_timeslot": "9am-1pm",
                    "wheelchair_handling_capable": False,
                    "has_conflict": True,
                }
            ],
        ],
    )

    options = matching_workspace_service.get_escort_options(trip_id)

    assert options[0].escort_id == escort_id
    assert options[0].issues == [
        "Escort already has a scheduled trip at this appointment time.",
        "Escort is unavailable at this appointment time.",
        "Escort cannot provide required wheelchair handling.",
    ]
