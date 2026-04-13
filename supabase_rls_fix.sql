-- =============================================================
-- supabase_rls_fix.sql
-- Run this in the Supabase SQL Editor to fix all RLS findings.
--
-- Strategy: Since this app uses FastAPI with its own JWT auth
-- and does NOT use Supabase's PostgREST API directly, we:
--   1. Enable RLS on every public table.
--   2. Deny all access to the `anon` and `authenticated` roles
--      (PostgREST roles) so no data leaks through the auto-API.
--   3. The FastAPI backend connects via the service role key
--      (bypasses RLS) so it is unaffected.
-- =============================================================

-- Step 1: Enable RLS on all public tables
ALTER TABLE public.alembic_version          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.department               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.holiday                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.leave_policy             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.project                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.attendance_session       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_log                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_leave_balance   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.leave_wfh_request        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.refresh_token            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_entry               ENABLE ROW LEVEL SECURITY;

-- Step 2: Revoke all direct PostgREST access (anon + authenticated roles)
-- This blocks all reads/writes through Supabase's auto-generated REST API.
-- Your FastAPI backend uses the service role key and is NOT affected.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;

-- Step 3: Add deny-all RLS policies as a defence-in-depth layer
-- (belt-and-suspenders: even if REVOKE is bypassed, RLS blocks access)
DO $$
DECLARE
    tbl TEXT;
    tables TEXT[] := ARRAY[
        'alembic_version', 'department', 'organization', 'holiday',
        'leave_policy', 'project', 'employee', 'attendance_session',
        'audit_log', 'employee_leave_balance', 'leave_wfh_request',
        'refresh_token', 'task_entry'
    ];
BEGIN
    FOREACH tbl IN ARRAY tables LOOP
        EXECUTE format(
            'CREATE POLICY deny_all_anon ON public.%I AS RESTRICTIVE
             FOR ALL TO anon, authenticated USING (false)',
            tbl
        );
    END LOOP;
END $$;
