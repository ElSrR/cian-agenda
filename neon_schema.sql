-- Extensiones (UUID)
create extension if not exists "pgcrypto";
create extension if not exists "uuid-ossp";

-- Tablas
create table if not exists public.patients (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  rut text,
  birth_date date,
  phone text,
  email text,
  created_at timestamptz not null default now()
);

create table if not exists public.professionals (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  specialty text,
  created_at timestamptz not null default now()
);

create table if not exists public.services (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  duration_minutes int not null default 30,
  price numeric not null default 30000,
  created_at timestamptz not null default now()
);

create table if not exists public.appointments (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid not null references public.patients(id) on delete restrict,
  professional_id uuid not null references public.professionals(id) on delete restrict,
  service_id uuid not null references public.services(id) on delete restrict,
  date date not null,
  start_time time not null,
  end_time time not null,
  status text not null default 'programada',
  notes text,
  price numeric not null default 0,
  created_at timestamptz not null default now()
);

-- Índices
create index if not exists idx_appt_date on public.appointments(date);
create index if not exists idx_appt_prof on public.appointments(professional_id);
create index if not exists idx_appt_patient on public.appointments(patient_id);

-- Trigger opcional: precio por defecto desde services
create or replace function set_appointment_price()
returns trigger as $$
begin
  if NEW.price is null or NEW.price = 0 then
    select s.price into NEW.price from public.services s where s.id = NEW.service_id;
  end if;
  return NEW;
end;
$$ language plpgsql;

drop trigger if exists trg_set_price on public.appointments;
create trigger trg_set_price before insert on public.appointments
for each row execute function set_appointment_price();

-- Vista de conveniencia
create or replace view public.v_appointments_full as
select a.*,
       p.full_name as patient_name,
       r.full_name as professional_name,
       s.name as service_name
from public.appointments a
left join public.patients p on p.id = a.patient_id
left join public.professionals r on r.id = a.professional_id
left join public.services s on s.id = a.service_id;
