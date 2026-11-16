create table public.profiles (id uuid primary key, email text, full_name text);
create table public.orders (id uuid primary key, user_id uuid, total numeric);
alter table public.orders enable row level security;
create policy "anyone" on public.orders for select using (true);
