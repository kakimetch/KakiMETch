from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
import re
from uuid import UUID

from app.database import get_connection
from app.schemas.match import EscortSuggestion, MatchResult

DIALECT_MATCH_SCORE = 2
GENDER_MATCH_SCORE = 1
TIMESLOT_PATTERN = re.compile(
    r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s*-\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))",
    re.IGNORECASE,
)


class TripNotFoundError(Exception):
    pass


class MatchingNotAllowedError(Exception):
    pass


def rank_escorts(
    client: Mapping[str, object],
    appt_date: date,
    appt_time: time,
    escorts: Sequence[Mapping[str, object]],
    limit: int = 3,
) -> MatchResult:
    """Hard-filter escort candidates, then rank survivors with simple match scores."""
    suggestions: list[EscortSuggestion] = []

    for escort in escorts:
        if get_hard_filter_issues(client, appt_date, appt_time, escort):
            continue

        score = 0
        flairs: list[str] = []
        if client.get("wheelchair_required"):
            flairs.append("Wheelchair capable")

        client_dialect = _as_text(client.get("dialect"))
        escort_dialects = _as_text_set(escort.get("dialects"))
        if client_dialect and client_dialect.casefold() in escort_dialects:
            score += DIALECT_MATCH_SCORE
            flairs.append(f"Speaks {client_dialect}")

        gender_preference = _as_text(client.get("gender_preference"))
        escort_gender = _as_text(escort.get("gender"))
        if gender_preference and escort_gender == gender_preference:
            score += GENDER_MATCH_SCORE
            flairs.append("Gender preference met")

        suggestions.append(
            EscortSuggestion(
                escort_id=str(escort["id"]),
                name=_as_text(escort.get("name")),
                gender=escort_gender,
                score=score,
                flairs=flairs,
            )
        )

    suggestions.sort(
        key=lambda suggestion: (-suggestion.score, suggestion.name.casefold())
    )
    suggestions = suggestions[:limit]
    warning = None
    if not suggestions:
        warning = "No viable escort is available. An admin can assign an escort with an override reason."

    return MatchResult(suggestions=suggestions, warning=warning)


def get_hard_filter_issues(
    client: Mapping[str, object],
    appt_date: date,
    appt_time: time,
    escort: Mapping[str, object],
) -> list[str]:
    """Return every hard constraint an escort fails for a specific appointment."""
    issues: list[str] = []

    if escort.get("has_conflict"):
        issues.append("Escort already has a scheduled trip at this appointment time.")
    if not is_available(escort, appt_date, appt_time):
        issues.append("Escort is unavailable at this appointment time.")
    if client.get("wheelchair_required") and not escort.get(
        "wheelchair_handling_capable"
    ):
        issues.append("Escort cannot provide required wheelchair handling.")

    return issues


def get_escort_suggestions(trip_id: UUID, limit: int = 3) -> MatchResult:
    """Load an accepted trip and return its ranked escort suggestions."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                    trips.escort_id,
                    trips.appt_date,
                    trips.appt_time,
                    trips.status,
                    elderly_clients.dialect,
                    elderly_clients.gender_preference,
                    elderly_clients.wheelchair_required,
                    elderly_clients.escort_required
                from public.trips
                join public.elderly_clients on elderly_clients.id = trips.elderly_id
                where trips.id = %s
                  and elderly_clients.deleted_at is null
                """,
                (trip_id,),
            )
            trip = cursor.fetchone()
            if trip is None:
                raise TripNotFoundError
            if trip["status"] not in ("accepted", "scheduled"):
                raise MatchingNotAllowedError
            if not trip["escort_required"]:
                return MatchResult(
                    suggestions=[],
                    warning="This trip does not require an escort.",
                )

            cursor.execute(
                """
                select
                    escorts.id,
                    escorts.name,
                    escorts.gender,
                    escorts.dialects,
                    escorts.available_days,
                    escorts.available_timeslot,
                    escorts.wheelchair_handling_capable,
                    exists (
                        select 1
                        from public.trips assigned_trips
                        where assigned_trips.escort_id = escorts.id
                          and assigned_trips.appt_date = %s
                          and assigned_trips.appt_time = %s
                          and assigned_trips.status = 'scheduled'
                          and assigned_trips.id <> %s
                    ) as has_conflict
                from public.escorts as escorts
                where %s is null or escorts.id <> %s
                """,
                (
                    trip["appt_date"],
                    trip["appt_time"],
                    trip_id,
                    trip["escort_id"],
                    trip["escort_id"],
                ),
            )
            escorts = cursor.fetchall()

    return rank_escorts(trip, trip["appt_date"], trip["appt_time"], escorts, limit)


def is_available(
    escort: Mapping[str, object], appt_date: date, appt_time: time
) -> bool:
    available_days = _as_text_set(escort.get("available_days"))
    if appt_date.strftime("%a").casefold() not in available_days:
        return False

    timeslot = _parse_timeslot(_as_text(escort.get("available_timeslot")))
    if timeslot is None:
        return False

    start_time, end_time = timeslot
    return start_time <= appt_time <= end_time


def _parse_timeslot(timeslot: str) -> tuple[time, time] | None:
    match = TIMESLOT_PATTERN.search(timeslot)
    if match is None:
        return None

    return (_parse_clock_time(match.group(1)), _parse_clock_time(match.group(2)))


def _parse_clock_time(value: str) -> time:
    normalized_value = value.replace(" ", "").upper()
    time_format = "%I:%M%p" if ":" in normalized_value else "%I%p"
    return datetime.strptime(normalized_value, time_format).time()


def _as_text_set(value: object) -> set[str]:
    if not isinstance(value, (list, tuple)):
        return set()

    return {_as_text(item).casefold() for item in value if _as_text(item)}


def _as_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""
