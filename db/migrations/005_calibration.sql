-- Blueprint v2 §2.6 — persist the calibrated probability and expected value per signal so the
-- calibration curve (p_hat vs realized) and EV-vs-outcome analysis are replayable historically.

alter table signals add column if not exists win_prob numeric;   -- calibrated P(target before stop)
alter table signals add column if not exists ev_r     numeric;   -- expected value in R, net of cost
