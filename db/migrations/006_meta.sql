-- Blueprint v2 §5 + §11 — meta-labeling shadow model.
-- Persist the full meta feature vector per signal (so any historical signal replays through any
-- future model version) and the meta-model's shadow probability for later calibration analysis.

alter table signals add column if not exists features jsonb;   -- ordered meta_features vector
alter table signals add column if not exists meta_p   numeric; -- meta-model P(win), shadow-logged
