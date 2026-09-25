-- VibeForge database schema. Run once in Supabase: SQL Editor → New query →
-- paste this file → Run.

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  html text not null,
  history text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists projects_user_updated_idx
  on public.projects (user_id, updated_at desc);

-- Only the backend (with the secret key, which bypasses RLS) touches this
-- table. RLS on with no policies = the public publishable key used by the
-- frontend can't read or write anything here directly.
alter table public.projects enable row level security;

-- Explicit grant for the backend's role, so this works even when the
-- project was created with "Automatically expose new tables" turned off.
grant select, insert, update, delete on public.projects to service_role;

-- One row per successful generation: powers the per-user daily limit
-- (backend/app/usage.py) and tells us which models are doing the work.
create table if not exists public.generations (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  model text not null,
  created_at timestamptz not null default now()
);

create index if not exists generations_user_created_idx
  on public.generations (user_id, created_at desc);

alter table public.generations enable row level security;
grant select, insert on public.generations to service_role;
