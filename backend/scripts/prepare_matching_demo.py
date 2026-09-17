from app.database import get_connection
from app.services.assessment_service import assess_trip


def prepare_matching_demo() -> tuple[int, int]:
    """Assess pending escort-required demo trips so the matching queue is usable."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                select trips.id
                from public.trips
                join public.elderly_clients
                    on elderly_clients.id = trips.elderly_id
                where trips.status = 'pending'
                  and elderly_clients.escort_required = true
                order by trips.appt_date, trips.appt_time
                """)
            trip_ids = [row["id"] for row in cursor.fetchall()]

    accepted = 0
    rejected = 0
    for trip_id in trip_ids:
        result = assess_trip(trip_id)
        if result.decision == "accepted":
            accepted += 1
        else:
            rejected += 1

    return accepted, rejected


if __name__ == "__main__":
    accepted_count, rejected_count = prepare_matching_demo()
    print(
        "Prepared matching demo: "
        f"{accepted_count} accepted, {rejected_count} rejected."
    )
