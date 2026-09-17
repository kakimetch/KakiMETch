-- KakiMETch complete MVP schema reference.
-- For a new Supabase project, run this file once.
-- For the existing project, apply the files in migrations/ in order instead.

create table public.elderly_clients (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    nric text,
    aic_registration_no text,
    postal_code text,
    block text,
    unit text,
    street_name text,
    address text,
    contact_no text,
    caregiver_name text,
    escort_required boolean not null default false,
    co_payment numeric(10, 2),
    date_of_birth date,
    nmts_effective_date date,
    nmts_expired_date date,
    date_of_entry date,
    action_updated_date text,
    lh_service_agreement text,
    sw_service_agreement text,
    wheelchair_required boolean not null default false,
    walking_frame_required boolean not null default false,
    caregiver_or_maid_available boolean,
    gender char(1) check (gender in ('M', 'F')),
    gender_preference char(1) check (gender_preference in ('M', 'F')),
    address_source text,
    dialect text,
    weight_kg numeric(5, 2) check (weight_kg is null or weight_kg > 0),
    nmtr_percentage numeric(5, 4) check (nmtr_percentage is null or (nmtr_percentage >= 0 and nmtr_percentage <= 1)),
    aic_mobility_status text not null default 'unknown'
        check (aic_mobility_status in ('ambulant', 'wheelchair_user', 'walking_frame_user', 'bed_bound', 'unknown')),
    lh_mobility_status text not null default 'unknown'
        check (lh_mobility_status in ('ambulant', 'wheelchair_user', 'walking_frame_user', 'bed_bound', 'unknown')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    deleted_at timestamptz,
    check (lh_service_agreement is null or lh_service_agreement in ('Y', 'N', 'Pending')),
    check (sw_service_agreement is null or sw_service_agreement in ('Y', 'N', 'Pending'))
);

create table public.escorts (
    id uuid primary key default gen_random_uuid(),
    external_id text unique,
    name text not null,
    gender char(1) not null check (gender in ('M', 'F')),
    dialects text[] not null default '{}',
    available_days text[] not null default '{}',
    available_timeslot text not null,
    wheelchair_handling_capable boolean not null default false,
    contact_no text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.trips (
    id uuid primary key default gen_random_uuid(),
    elderly_id uuid not null references public.elderly_clients(id) on delete restrict,
    escort_id uuid references public.escorts(id) on delete set null,
    appt_date date not null,
    appt_time time not null,
    destination text not null,
    status text not null default 'pending'
        check (status in ('pending', 'accepted', 'rejected', 'scheduled')),
    assessment_reasons jsonb not null default '[]'::jsonb,
    assessment_warnings jsonb not null default '[]'::jsonb,
    assessed_at timestamptz,
    assignment_override boolean not null default false,
    assignment_override_reason text,
    confirmed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (
        (assignment_override = false and assignment_override_reason is null)
        or (assignment_override = true and length(trim(assignment_override_reason)) > 0)
    ),
    check (status <> 'scheduled' or escort_id is not null)
);

create index trips_status_appt_date_idx on public.trips (status, appt_date);
create index trips_escort_appointment_idx on public.trips (escort_id, appt_date, appt_time)
    where status = 'scheduled';
create index trips_elderly_id_idx on public.trips (elderly_id);
create unique index elderly_clients_active_nric_idx
    on public.elderly_clients (nric)
    where deleted_at is null and nric is not null;
create index elderly_clients_active_name_idx
    on public.elderly_clients (name)
    where deleted_at is null;
