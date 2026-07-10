-- Blueprint v2 §6.4 — arbitrage opportunity log (funding carry first).
-- Records every positive-EV-after-cost opportunity the detector finds, so the data itself proves
-- whether/when the carry is real at our size and latency.

create table if not exists arb_opportunities (
    id                  bigint generated always as identity primary key,
    ts                  timestamptz not null default now(),
    type                text not null,          -- 'funding_carry'
    symbol              text not null,
    expected_collection numeric,                -- forecast funding over the horizon (fraction)
    cost                numeric,                -- round-trip cost of both legs (fraction)
    ev                  numeric,                -- expected value after cost (fraction)
    annualized_yield    numeric,
    half_life           numeric,                -- funding mean-reversion half-life (periods)
    horizon_periods     int,
    positive            boolean
);
create index if not exists arb_opps_ts on arb_opportunities (ts desc);
