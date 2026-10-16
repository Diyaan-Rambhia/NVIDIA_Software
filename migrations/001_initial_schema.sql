-- Migration: 001_initial_schema.sql
-- Description: Core database schema and Row-Level Security policies for FinInsight.
-- Requirements: PROJECT.md §7.1, §4.2, §4.3 and PROGRESS.md X2.1.
-- Constraint: Additive and re-runnable only (no DROP, TRUNCATE, or DELETE).

-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Reference Table: Plans (populated from config/plans.yaml)
CREATE TABLE IF NOT EXISTS public.plans (
    id TEXT PRIMARY KEY,
    segment TEXT NOT NULL CHECK (segment IN ('retail', 'institutional', 'internal')),
    name TEXT NOT NULL,
    price_inr_monthly NUMERIC(10, 2) NOT NULL DEFAULT 0.00
);

ALTER TABLE public.plans ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'plans' AND policyname = 'plans_select_all'
    ) THEN
        CREATE POLICY plans_select_all ON public.plans
            FOR SELECT USING (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'plans' AND policyname = 'plans_service_role_modify'
    ) THEN
        CREATE POLICY plans_service_role_modify ON public.plans
            FOR ALL USING (auth.role() = 'service_role');
    END IF;
END $$;

-- Populate plans additively
INSERT INTO public.plans (id, segment, name, price_inr_monthly)
VALUES
    ('retail_free', 'retail', 'Retail Free', 0.00),
    ('retail_paid', 'retail', 'Retail Paid', 999.00),
    ('institutional_free', 'institutional', 'Institutional Free', 0.00),
    ('institutional_paid', 'institutional', 'Institutional Paid', 4999.00),
    ('judge_all', 'internal', 'Judge All', 0.00)
ON CONFLICT (id) DO UPDATE SET
    segment = EXCLUDED.segment,
    name = EXCLUDED.name,
    price_inr_monthly = EXCLUDED.price_inr_monthly;

-- 2. User Profiles
CREATE TABLE IF NOT EXISTS public.profiles (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    segment TEXT NOT NULL CHECK (segment IN ('retail', 'institutional', 'internal')),
    plan TEXT NOT NULL REFERENCES public.plans(id),
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    tos_accepted_version TEXT,
    tos_accepted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'profiles' AND policyname = 'profiles_select_own'
    ) THEN
        CREATE POLICY profiles_select_own ON public.profiles
            FOR SELECT USING (auth.uid() = user_id OR auth.role() = 'service_role');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'profiles' AND policyname = 'profiles_insert_own_free'
    ) THEN
        CREATE POLICY profiles_insert_own_free ON public.profiles
            FOR INSERT WITH CHECK (
                (auth.uid() = user_id AND plan IN ('retail_free', 'institutional_free') AND role = 'user' AND status = 'active')
                OR auth.role() = 'service_role'
            );
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'profiles' AND policyname = 'profiles_service_role_update'
    ) THEN
        CREATE POLICY profiles_service_role_update ON public.profiles
            FOR UPDATE USING (auth.role() = 'service_role')
            WITH CHECK (auth.role() = 'service_role');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'profiles' AND policyname = 'profiles_service_role_delete'
    ) THEN
        CREATE POLICY profiles_service_role_delete ON public.profiles
            FOR DELETE USING (auth.role() = 'service_role');
    END IF;
END $$;

-- 3. Daily Usage Quota Counters
CREATE TABLE IF NOT EXISTS public.usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    feature TEXT NOT NULL CHECK (feature IN ('contagion', 'filing_consistency', 'investment_log')),
    utc_date DATE NOT NULL,
    count INT NOT NULL DEFAULT 0 CHECK (count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_usage_user_feature_date UNIQUE (user_id, feature, utc_date)
);

ALTER TABLE public.usage ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'usage' AND policyname = 'usage_select_own'
    ) THEN
        CREATE POLICY usage_select_own ON public.usage
            FOR SELECT USING (auth.uid() = user_id OR auth.role() = 'service_role');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'usage' AND policyname = 'usage_service_role_modify'
    ) THEN
        CREATE POLICY usage_service_role_modify ON public.usage
            FOR ALL USING (auth.role() = 'service_role')
            WITH CHECK (auth.role() = 'service_role');
    END IF;
END $$;

-- 4. Institutional Regulator Registration Submissions
CREATE TABLE IF NOT EXISTS public.institutional_verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    regulator TEXT NOT NULL DEFAULT 'SEBI',
    registration_number TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    reviewed_at TIMESTAMPTZ,
    reviewed_by UUID REFERENCES auth.users(id),
    rejection_reason TEXT
);

ALTER TABLE public.institutional_verifications ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'institutional_verifications' AND policyname = 'inst_verif_select_own'
    ) THEN
        CREATE POLICY inst_verif_select_own ON public.institutional_verifications
            FOR SELECT USING (auth.uid() = user_id OR auth.role() = 'service_role');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'institutional_verifications' AND policyname = 'inst_verif_insert_own_pending'
    ) THEN
        CREATE POLICY inst_verif_insert_own_pending ON public.institutional_verifications
            FOR INSERT WITH CHECK (
                (auth.uid() = user_id AND status = 'pending')
                OR auth.role() = 'service_role'
            );
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'institutional_verifications' AND policyname = 'inst_verif_service_role_update'
    ) THEN
        CREATE POLICY inst_verif_service_role_update ON public.institutional_verifications
            FOR UPDATE USING (auth.role() = 'service_role')
            WITH CHECK (auth.role() = 'service_role');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'institutional_verifications' AND policyname = 'inst_verif_service_role_delete'
    ) THEN
        CREATE POLICY inst_verif_service_role_delete ON public.institutional_verifications
            FOR DELETE USING (auth.role() = 'service_role');
    END IF;
END $$;

-- 5. Subscriptions
CREATE TABLE IF NOT EXISTS public.subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    plan TEXT NOT NULL REFERENCES public.plans(id),
    status TEXT NOT NULL CHECK (status IN ('active', 'canceled', 'past_due', 'trialing')),
    current_period_end TIMESTAMPTZ,
    gateway_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'subscriptions' AND policyname = 'subscriptions_select_own'
    ) THEN
        CREATE POLICY subscriptions_select_own ON public.subscriptions
            FOR SELECT USING (auth.uid() = user_id OR auth.role() = 'service_role');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'subscriptions' AND policyname = 'subscriptions_service_role_modify'
    ) THEN
        CREATE POLICY subscriptions_service_role_modify ON public.subscriptions
            FOR ALL USING (auth.role() = 'service_role')
            WITH CHECK (auth.role() = 'service_role');
    END IF;
END $$;

-- 6. Payments
CREATE TABLE IF NOT EXISTS public.payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    gateway_ids JSONB NOT NULL DEFAULT '{}'::jsonb,
    amount_inr NUMERIC(12, 2) NOT NULL CHECK (amount_inr >= 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    status TEXT NOT NULL CHECK (status IN ('created', 'authorized', 'captured', 'refunded', 'failed')),
    plan TEXT NOT NULL REFERENCES public.plans(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'payments' AND policyname = 'payments_select_own'
    ) THEN
        CREATE POLICY payments_select_own ON public.payments
            FOR SELECT USING (auth.uid() = user_id OR auth.role() = 'service_role');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'payments' AND policyname = 'payments_service_role_modify'
    ) THEN
        CREATE POLICY payments_service_role_modify ON public.payments
            FOR ALL USING (auth.role() = 'service_role')
            WITH CHECK (auth.role() = 'service_role');
    END IF;
END $$;

-- 7. LLM Usage Ledger
CREATE TABLE IF NOT EXISTS public.llm_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    route TEXT NOT NULL,
    alias TEXT NOT NULL,
    model_id TEXT NOT NULL,
    input_tokens INT NOT NULL CHECK (input_tokens >= 0),
    output_tokens INT NOT NULL CHECK (output_tokens >= 0),
    est_cost_usd NUMERIC(10, 6) NOT NULL CHECK (est_cost_usd >= 0),
    cache_hit BOOLEAN NOT NULL DEFAULT false
);

ALTER TABLE public.llm_ledger ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'llm_ledger' AND policyname = 'llm_ledger_select_own'
    ) THEN
        CREATE POLICY llm_ledger_select_own ON public.llm_ledger
            FOR SELECT USING (auth.uid() = user_id OR auth.role() = 'service_role');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'llm_ledger' AND policyname = 'llm_ledger_service_role_modify'
    ) THEN
        CREATE POLICY llm_ledger_service_role_modify ON public.llm_ledger
            FOR ALL USING (auth.role() = 'service_role')
            WITH CHECK (auth.role() = 'service_role');
    END IF;
END $$;

-- 8. Analytical Results
CREATE TABLE IF NOT EXISTS public.results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    payload_json JSONB NOT NULL,
    provenance_json JSONB NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

ALTER TABLE public.results ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'results' AND policyname = 'results_select_own'
    ) THEN
        CREATE POLICY results_select_own ON public.results
            FOR SELECT USING (auth.uid() = user_id OR auth.role() = 'service_role');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'results' AND policyname = 'results_insert_own'
    ) THEN
        CREATE POLICY results_insert_own ON public.results
            FOR INSERT WITH CHECK (auth.uid() = user_id OR auth.role() = 'service_role');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'results' AND policyname = 'results_service_role_modify'
    ) THEN
        CREATE POLICY results_service_role_modify ON public.results
            FOR UPDATE USING (auth.role() = 'service_role')
            WITH CHECK (auth.role() = 'service_role');
    END IF;
END $$;

-- 9. System and Audit Events
CREATE TABLE IF NOT EXISTS public.events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    kind TEXT NOT NULL,
    subject TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_ms INT,
    details_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'events' AND policyname = 'events_service_role_all'
    ) THEN
        CREATE POLICY events_service_role_all ON public.events
            FOR ALL USING (auth.role() = 'service_role')
            WITH CHECK (auth.role() = 'service_role');
    END IF;
END $$;
