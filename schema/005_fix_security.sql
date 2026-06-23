-- =============================================================
-- 005_fix_security.sql — Fix 4 Supabase Advisor security warnings
-- =============================================================
-- Applied via MCP on 2026-06-22 in response to Advisor scan.
--
-- (a) Three legacy views still had SECURITY DEFINER property
--     (security_invoker=false by default). Flip them so they
--     enforce the QUERYING user's RLS + grants, not the view
--     creator's. Matches the pattern used on all views created
--     since v2 (dw_wages, dw_contract, dw_autonomous, etc.).
--
-- (b) fact_autonomous (created 2026-06-22 in 004_fact_autonomous.sql)
--     forgot to enable RLS. Enable it + add a SELECT policy for the
--     anon + authenticated roles, matching the pattern on the other
--     fact_* tables in domestic_work.
--
-- Idempotent-ish: ALTER VIEW SET is idempotent; CREATE POLICY will
-- fail on rerun if the policy already exists. If you need to rerun,
-- drop the policy first or wrap in CREATE POLICY IF NOT EXISTS via
-- a DO block.
-- =============================================================

alter view public.dw_hours   set (security_invoker = true);
alter view public.dw_prev    set (security_invoker = true);
alter view public.dw_workers set (security_invoker = true);

alter table domestic_work.fact_autonomous enable row level security;

create policy "Read for anon and authenticated"
  on domestic_work.fact_autonomous
  for select
  to anon, authenticated
  using (true);

-- Sanity
do $$
declare n int;
begin
  select count(*) into n
  from pg_policies
  where schemaname = 'domestic_work'
    and tablename = 'fact_autonomous';
  if n < 1 then
    raise exception 'Expected at least 1 policy on fact_autonomous, found %', n;
  end if;
  raise notice 'OK: % policies on fact_autonomous', n;
end$$;
