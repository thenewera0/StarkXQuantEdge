-- Universal Signal Cockpit — initial schema (Supabase / Postgres)
-- Run in the Supabase SQL editor, or via `supabase db push` once the project exists.
-- Phase 1a runs entirely without this DB; it lands here for Phase 1b/2/3 persistence.

create extension if not exists vector;        -- pgvector for Phase 3 memory

-- Watchlist of tracked symbols + timeframes.
create table if not exists watchlist (
    id          bigint generated always as identity primary key,
    symbol      text not null,
    interval    text not null,
    market      text not null default 'crypto',
    active      boolean not null default true,
    created_at  timestamptz not null default now(),
    unique (symbol, interval)
);

-- Every generated signal with its full context.
create table if not exists signals (
    id           bigint generated always as identity primary key,
    symbol       text not null,
    interval     text not null,
    as_of        timestamptz not null,        -- the closed-bar time the signal is for
    label        text not null,               -- Strong Sell .. Strong Buy
    composite    numeric not null,            -- -100..100
    confidence   numeric not null,            -- 0..100
    regime       text,                        -- placeholder until Phase 3 regime detection
    price        numeric,
    atr          numeric,
    rationale    text,                        -- LLM narrative (Phase 1b)
    entry        numeric,
    stop         numeric,
    target       numeric,
    created_at   timestamptz not null default now()
);
create index if not exists signals_symbol_time on signals (symbol, as_of desc);

-- Per-category scores for each signal (the raw material for later learning).
create table if not exists factor_logs (
    id          bigint generated always as identity primary key,
    signal_id   bigint not null references signals(id) on delete cascade,
    trend       numeric,
    momentum    numeric,
    volatility  numeric,
    structure   numeric,
    flow        numeric,
    sentiment   numeric,
    macro       numeric,
    consensus   numeric
);

-- Resolved outcome per signal. No outcomes = nothing to learn from.
create table if not exists outcomes (
    id           bigint generated always as identity primary key,
    signal_id    bigint not null references signals(id) on delete cascade,
    resolved_at  timestamptz,
    result       text,                        -- 'target' | 'stop' | 'timeout' | 'manual'
    pnl          numeric,                     -- net of fees + slippage, fraction
    mfe          numeric,                     -- max favorable excursion
    mae          numeric,                     -- max adverse excursion
    bars_held    int
);

-- Cost ledger: every LLM/search call so the Cost-Saver toggle shows real savings.
create table if not exists cost_log (
    id          bigint generated always as identity primary key,
    ts          timestamptz not null default now(),
    kind        text not null,               -- 'llm' | 'search'
    provider    text,
    model       text,
    tokens_in   int,
    tokens_out  int,
    usd         numeric
);

-- Per-regime weight profiles (Phase 3 adaptive weighting; champion/challenger).
create table if not exists regime_weights (
    id          bigint generated always as identity primary key,
    regime      text not null,
    interval    text not null,
    weights     jsonb not null,
    is_champion boolean not null default false,
    created_at  timestamptz not null default now()
);

-- pgvector memory of past market situations (Phase 3, experimental).
create table if not exists memory_embeddings (
    id          bigint generated always as identity primary key,
    signal_id   bigint references signals(id) on delete set null,
    embedding   vector(384),                 -- adjust to the embedding model used
    note        text,
    created_at  timestamptz not null default now()
);

-- App settings (mode toggle, etc.).
create table if not exists settings (
    key         text primary key,
    value       jsonb not null,
    updated_at  timestamptz not null default now()
);
insert into settings (key, value)
values ('mode', '"research"')
on conflict (key) do nothing;
