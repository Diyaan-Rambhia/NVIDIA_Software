-- Migration: 002_nullable_llm_ledger_cost.sql
-- Description: Allow NULL for est_cost_usd in llm_ledger when tier pricing is unset.

DO $$ BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'llm_ledger'
          AND column_name = 'est_cost_usd'
          AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE public.llm_ledger ALTER COLUMN est_cost_usd DROP NOT NULL;
    END IF;
END $$;
