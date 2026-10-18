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

-- Sites their owners chose to publish at <frontend>/s/<slug>. One row per
-- project; publishing again updates the HTML under the same slug.
create table if not exists public.published_sites (
  slug text primary key,
  project_id uuid not null unique references public.projects (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  html text not null,
  published_at timestamptz not null default now()
);

alter table public.published_sites enable row level security;
grant select, insert, update, delete on public.published_sites to service_role;

-- Published pages are public by definition: anyone (the publishable key's
-- `anon` role, used by the Vercel function that serves /s/<slug>) may read
-- a page's slug and HTML — and nothing else, not even who owns it.
grant select (slug, html) on public.published_sites to anon;
drop policy if exists "Published sites are public" on public.published_sites;
create policy "Published sites are public"
  on public.published_sites for select to anon using (true);

-- Every version of every site: one row per successful generation or
-- restore, so the owner can look back and restore an earlier one.
create table if not exists public.project_versions (
  id bigint generated always as identity primary key,
  project_id uuid not null references public.projects (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  prompt text not null,
  html text not null,
  created_at timestamptz not null default now()
);

create index if not exists project_versions_project_created_idx
  on public.project_versions (project_id, created_at);

alter table public.project_versions enable row level security;
grant select, insert, delete on public.project_versions to service_role;

-- A name the owner gave the site (null = called by its first request).
alter table public.projects add column if not exists name text;

-- The person's own photos for their sites (backend/app/user_photos.py). The
-- files live in the public Storage bucket "site-photos", one folder per
-- user; a row per photo says whose it is and which site it was added to.
create table if not exists public.site_photos (
  id uuid primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  project_id uuid references public.projects (id) on delete set null,
  path text not null,
  sent boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists site_photos_user_idx on public.site_photos (user_id, created_at);

alter table public.site_photos enable row level security;
grant select, insert, update, delete on public.site_photos to service_role;

-- Public: a site's visitors load its photos straight from Storage. Only the
-- backend (secret key) can upload or delete; the size and types match what
-- user_photos.py accepts.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('site-photos', 'site-photos', true, 2000000, array['image/webp', 'image/jpeg', 'image/png'])
on conflict (id) do nothing;

-- Which Telegram chat gets an account's form submissions (backend/app/leads.py).
-- `code` is the one-time code in the "Connect Telegram" link.
create table if not exists public.telegram_links (
  user_id uuid primary key references auth.users (id) on delete cascade,
  chat_id bigint,
  code text unique,
  code_expires_at timestamptz,
  updated_at timestamptz not null default now()
);

alter table public.telegram_links enable row level security;
grant select, insert, update, delete on public.telegram_links to service_role;

-- What visitors sent through forms on published sites. Kept so nothing is
-- lost when Telegram isn't connected or is down; goes with the site.
create table if not exists public.form_submissions (
  id bigint generated always as identity primary key,
  project_id uuid not null references public.projects (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  fields jsonb not null,
  delivered boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists form_submissions_user_created_idx
  on public.form_submissions (user_id, created_at desc);

alter table public.form_submissions enable row level security;
grant select, insert, delete on public.form_submissions to service_role;

-- Visits to published sites (backend/app/visits.py). No IP addresses: only an
-- anonymous per-day code to tell unique visitors apart. Goes with the site.
create table if not exists public.site_visits (
  id bigint generated always as identity primary key,
  project_id uuid not null references public.projects (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  visitor text not null,
  created_at timestamptz not null default now()
);

create index if not exists site_visits_project_created_idx
  on public.site_visits (project_id, created_at desc);

alter table public.site_visits enable row level security;
grant select, insert, delete on public.site_visits to service_role;

-- Support requests and ideas sent by users (backend/app/feedback.py).
-- Kept so nothing is lost when the owner's Telegram isn't connected.
create table if not exists public.feedback (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  email text not null default '',
  kind text not null,
  message text not null,
  created_at timestamptz not null default now()
);

alter table public.feedback enable row level security;
grant select, insert, delete on public.feedback to service_role;

-- Search engines may list a published site only if its owner switched that on
-- (default: no). Public, like the page itself: the Vercel function that serves
-- /s/<slug> sets the robots header from it, and /sitemap.xml lists these.
alter table public.published_sites add column if not exists indexable boolean not null default false;
grant select (indexable, published_at) on public.published_sites to anon;

-- A link for a client to look at a site and leave comments
-- (backend/app/reviews.py). One link per site, switched off by deleting it.
-- Only the backend touches these tables: the link's token is the key.
create table if not exists public.reviews (
  project_id uuid primary key references public.projects (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  token text not null unique,
  created_at timestamptz not null default now()
);

alter table public.reviews enable row level security;
grant select, insert, delete on public.reviews to service_role;

create table if not exists public.review_comments (
  id bigint generated always as identity primary key,
  project_id uuid not null references public.projects (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  author text not null default '',
  text text not null,
  selector text not null default '',
  label text not null default '',
  resolved boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists review_comments_project_idx
  on public.review_comments (project_id, id);

alter table public.review_comments enable row level security;
grant select, insert, update, delete on public.review_comments to service_role;

-- The site a person is working on in the Telegram chat (backend/app/chat_sites.py):
-- plain messages change it, /new clears it.
alter table public.telegram_links
  add column if not exists active_project_id uuid references public.projects (id) on delete set null;
