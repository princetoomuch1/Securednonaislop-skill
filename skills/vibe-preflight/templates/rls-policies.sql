-- vibe-preflight: owner-scoped RLS template for Supabase.
-- Replace <table> and user_id with your names. Run in a migration, test with TWO real accounts.

alter table public.<table> enable row level security;
alter table public.<table> force row level security;

-- Read own rows
create policy "<table>_select_own" on public.<table>
  for select to authenticated
  using ((select auth.uid()) = user_id);

-- Insert only as yourself
create policy "<table>_insert_own" on public.<table>
  for insert to authenticated
  with check ((select auth.uid()) = user_id);

-- Update own rows, cannot reassign owner
create policy "<table>_update_own" on public.<table>
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

-- Delete own rows
create policy "<table>_delete_own" on public.<table>
  for delete to authenticated
  using ((select auth.uid()) = user_id);

-- Index the policy column (RLS performance)
create index if not exists <table>_user_id_idx on public.<table> (user_id);

-- Public lookup table (countries, plans): read-only for everyone, no writes
-- create policy "<lookup>_read_all" on public.<lookup> for select to anon, authenticated using (true);

-- Lock down functions
-- revoke execute on function public.<fn> from anon, public;

-- Verify: should list zero rows
-- select relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
-- where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity;
