alter table public.elderly_clients
add column deleted_at timestamptz;

alter table public.elderly_clients
drop constraint elderly_clients_nric_key;

create unique index elderly_clients_active_nric_idx
on public.elderly_clients (nric)
where deleted_at is null and nric is not null;

create index elderly_clients_active_name_idx
on public.elderly_clients (name)
where deleted_at is null;
