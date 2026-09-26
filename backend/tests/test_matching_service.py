from datetime import date, time

from app.services.matching_service import rank_escorts

CLIENT = {
    "dialect": "Hokkien",
    "gender_preference": "F",
    "wheelchair_required": True,
}
APPOINTMENT_DATE = date(2026, 9, 1)  # Tuesday
APPOINTMENT_TIME = time(10, 0)


def test_ranking_filters_unavailable_and_conflicting_escorts():
    escorts = [
        {
            "id": "best-match",
            "name": "Mei Ling",
            "gender": "F",
            "dialects": ["Hokkien", "English"],
            "available_days": ["Tue"],
            "available_timeslot": "9am-1pm",
            "wheelchair_handling_capable": True,
            "has_conflict": False,
        },
        {
            "id": "dialect-only",
            "name": "Wei Ming",
            "gender": "M",
            "dialects": ["Hokkien"],
            "available_days": ["Tue"],
            "available_timeslot": "9am-1pm",
            "wheelchair_handling_capable": True,
            "has_conflict": False,
        },
        {
            "id": "no-wheelchair",
            "name": "Siew Yin",
            "gender": "F",
            "dialects": ["Hokkien"],
            "available_days": ["Tue"],
            "available_timeslot": "9am-1pm",
            "wheelchair_handling_capable": False,
            "has_conflict": False,
        },
        {
            "id": "conflicting",
            "name": "Kok Seng",
            "gender": "F",
            "dialects": ["Hokkien"],
            "available_days": ["Tue"],
            "available_timeslot": "9am-1pm",
            "wheelchair_handling_capable": True,
            "has_conflict": True,
        },
    ]

    result = rank_escorts(CLIENT, APPOINTMENT_DATE, APPOINTMENT_TIME, escorts)

    assert [suggestion.escort_id for suggestion in result.suggestions] == [
        "best-match",
        "dialect-only",
    ]
    assert result.suggestions[0].score == 3
    assert result.suggestions[0].flairs == [
        "Wheelchair capable",
        "Speaks Hokkien",
        "Gender preference met",
    ]


def test_ranking_returns_a_warning_when_no_viable_escort_exists():
    escorts = [
        {
            "id": "unavailable",
            "name": "Unavailable Escort",
            "gender": "F",
            "dialects": ["Hokkien"],
            "available_days": ["Mon"],
            "available_timeslot": "9am-1pm",
            "wheelchair_handling_capable": True,
            "has_conflict": False,
        }
    ]

    result = rank_escorts(CLIENT, APPOINTMENT_DATE, APPOINTMENT_TIME, escorts)

    assert result.suggestions == []
    assert result.warning == (
        "No viable escort is available. An admin can assign an escort with an override reason."
    )
