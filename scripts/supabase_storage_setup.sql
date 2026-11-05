-- Run once in the Supabase SQL editor as an administrator.
-- The application uses a PRIVATE Storage bucket (create it in Storage settings),
-- SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY and SUPABASE_STORAGE_BUCKET.
-- Never expose the service-role key to a browser. No public Storage policy is needed.
-- These cooperative locks deliberately NEVER expire: expiring a lock while an old
-- HTTP upload is still in flight permits stale overwrites. All source overwrites
-- must use acquire_source_update_lock/release_source_update_lock.
create table if not exists public.source_update_locks (
    object_key text primary key,
    owner_token uuid not null,
    acquired_at timestamptz not null default now()
);
alter table public.source_update_locks enable row level security;
revoke all on public.source_update_locks from public, anon, authenticated;

create or replace function public.acquire_source_update_lock(p_object_key text, p_owner_token uuid)
returns boolean language plpgsql security definer set search_path = '' as $$
begin
    if p_object_key is null or p_object_key = '' or p_owner_token is null then
        raise exception 'Invalid lock identity';
    end if;
    insert into public.source_update_locks(object_key, owner_token)
        values (p_object_key, p_owner_token) on conflict (object_key) do nothing;
    return found;
end;
$$;
create or replace function public.release_source_update_lock(p_object_key text, p_owner_token uuid)
returns boolean language plpgsql security definer set search_path = '' as $$
begin
    delete from public.source_update_locks
        where object_key = p_object_key and owner_token = p_owner_token;
    return found;
end;
$$;
revoke all on function public.acquire_source_update_lock(text, uuid) from public, anon, authenticated;
revoke all on function public.release_source_update_lock(text, uuid) from public, anon, authenticated;
grant execute on function public.acquire_source_update_lock(text, uuid) to service_role;
grant execute on function public.release_source_update_lock(text, uuid) to service_role;

-- ADMIN RECOVERY ONLY: after a crash/ambiguous network response, a lock may remain.
-- FIRST stop every writer and establish that no old upload can still complete.
-- Inspect the original and backups, reconcile uncertain writes, THEN explicitly
-- delete the affected row as administrator. Never schedule automatic lock cleanup.
-- select object_key, acquired_at from public.source_update_locks;
-- delete from public.source_update_locks where object_key = '<verified object key>';
