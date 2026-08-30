-- InterMesh portal — Supabase schema
--
-- Run once in the Supabase SQL editor, or with `supabase db push`.
--
-- Two rules shape everything below.
--
--  1. Row Level Security is the access control. The anon key is public by
--     design; a table without policies is either unreadable or wide open,
--     never "protected by the key being secret".
--
--  2. An API key is stored as a SHA-256 digest and a short prefix, never in
--     clear. This mirrors what the hub already does in `intermesh.apikeys`:
--     it can verify a key, never reveal one. The plaintext exists once, in
--     the response to its creation, and is unrecoverable afterwards.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- Organizations
-- ---------------------------------------------------------------------------

create table if not exists public.organizations (
  id          uuid primary key default gen_random_uuid(),
  -- `slug` becomes the org_id namespacing every agent: acme/pricing_engine.
  -- The check mirrors the normalisation the signup form shows while typing.
  slug        text not null unique check (slug ~ '^[a-z0-9][a-z0-9-]{0,38}[a-z0-9]$'),
  name        text not null,
  created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Memberships
-- ---------------------------------------------------------------------------

create type public.member_role as enum ('owner', 'admin', 'member', 'viewer');

create table if not exists public.memberships (
  id          uuid primary key default gen_random_uuid(),
  org_id      uuid not null references public.organizations(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  role        public.member_role not null default 'member',
  created_at  timestamptz not null default now(),
  unique (org_id, user_id)
);

create index if not exists memberships_user_idx on public.memberships(user_id);
create index if not exists memberships_org_idx on public.memberships(org_id);

-- ---------------------------------------------------------------------------
-- API keys
-- ---------------------------------------------------------------------------

create table if not exists public.api_keys (
  id           uuid primary key default gen_random_uuid(),
  org_id       uuid not null references public.organizations(id) on delete cascade,
  name         text not null,
  -- Digest of the full key. `prefix` is the first characters, kept only so a
  -- human can tell two keys apart in a list.
  key_digest   text not null unique,
  prefix       text not null,
  role         text not null default 'worker',
  created_by   uuid references auth.users(id) on delete set null,
  created_at   timestamptz not null default now(),
  last_used_at timestamptz,
  revoked_at   timestamptz
);

create index if not exists api_keys_org_idx on public.api_keys(org_id);

-- ---------------------------------------------------------------------------
-- Helper: which organizations does the caller belong to?
--
-- SECURITY DEFINER with a pinned search_path. Without it, a policy that reads
-- `memberships` would itself be filtered by the policy on `memberships`, and
-- Postgres would recurse.
-- ---------------------------------------------------------------------------

create or replace function public.caller_org_ids()
returns setof uuid
language sql
stable
security definer
set search_path = public
as $$
  select org_id from public.memberships where user_id = auth.uid();
$$;

create or replace function public.caller_is_org_admin(target uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.memberships
    where user_id = auth.uid()
      and org_id = target
      and role in ('owner', 'admin')
  );
$$;

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------

alter table public.organizations enable row level security;
alter table public.memberships   enable row level security;
alter table public.api_keys      enable row level security;

-- Organizations: readable by their members; creatable by any signed-in user
-- (the trigger below immediately makes the creator its owner).
drop policy if exists "org readable by members" on public.organizations;
create policy "org readable by members" on public.organizations
  for select using (id in (select public.caller_org_ids()));

drop policy if exists "org creatable by authenticated" on public.organizations;
create policy "org creatable by authenticated" on public.organizations
  for insert to authenticated with check (true);

drop policy if exists "org updatable by admins" on public.organizations;
create policy "org updatable by admins" on public.organizations
  for update using (public.caller_is_org_admin(id));

-- Memberships: a member sees the roster of their own organizations.
drop policy if exists "memberships readable by org members" on public.memberships;
create policy "memberships readable by org members" on public.memberships
  for select using (org_id in (select public.caller_org_ids()));

drop policy if exists "memberships writable by admins" on public.memberships;
create policy "memberships writable by admins" on public.memberships
  for all using (public.caller_is_org_admin(org_id))
  with check (public.caller_is_org_admin(org_id));

-- API keys: visible to the organization, mutable by its admins only.
drop policy if exists "keys readable by org members" on public.api_keys;
create policy "keys readable by org members" on public.api_keys
  for select using (org_id in (select public.caller_org_ids()));

drop policy if exists "keys writable by admins" on public.api_keys;
create policy "keys writable by admins" on public.api_keys
  for all using (public.caller_is_org_admin(org_id))
  with check (public.caller_is_org_admin(org_id));

-- ---------------------------------------------------------------------------
-- The creator of an organization becomes its owner.
--
-- Done in a trigger rather than in the client: two round trips leave a window
-- where an organization exists with nobody able to read it, and the second
-- call can simply fail.
-- ---------------------------------------------------------------------------

create or replace function public.claim_new_organization()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.memberships (org_id, user_id, role)
  values (new.id, auth.uid(), 'owner');
  return new;
end;
$$;

drop trigger if exists on_organization_created on public.organizations;
create trigger on_organization_created
  after insert on public.organizations
  for each row execute function public.claim_new_organization();
