-- Migration 011: Research Scorecard & Trials Ledger (Phase 1 Bar-Level Research Harness)

create table if not exists research_scorecard (
    id bigserial primary key,
    factor_name text not null,
    horizon_bars integer not null,
    pooled_ic numeric(8, 4),
    pooled_p numeric(8, 4),
    daily_mean_ic numeric(8, 4),
    daily_t numeric(8, 4),
    mirror_pos_ic numeric(8, 4),
    mirror_neg_ic numeric(8, 4),
    q5_q1_spread_bps numeric(10, 2),
    autocorr numeric(8, 4),
    quarter_stability_pct numeric(6, 2),
    verdict text not null,
    tested_at timestamptz not null default now()
);

create table if not exists research_trials (
    id bigserial primary key,
    trial_name text not null,
    description text,
    sharpe_raw numeric(8, 4),
    deflated_sharpe numeric(8, 4),
    pbo numeric(8, 4),
    trial_counter integer not null,
    recorded_at timestamptz not null default now()
);

create index if not exists idx_research_scorecard_factor on research_scorecard (factor_name, horizon_bars);
