# Acceptance checklist — current-affairs law-link patch

- [ ] Rule registry validates all positive and negative examples.
- [ ] Minimum-wage event links to `最低工資法` without claiming a law amendment.
- [ ] Enterprise-childcare event links to `性別平等工作法` Article 23.
- [ ] Public childcare without employer/workplace context does not inherit the employer-childcare law rule.
- [ ] Newly inferred law causes historical law/topic statistics to be recomputed.
- [ ] `current_affairs_signals.json`, `current_affairs_events.json`, and `current_affairs_trends.json` rebuild from exact PR head.
- [ ] `current_affairs_signals_smoke.py` passes.
- [ ] `current_affairs_events_smoke.py` passes.
- [ ] `public_monitoring_v2_smoke.py` passes.
- [ ] `auto/` and `cdn/auto/` rebuilt snapshot pairs are identical.
- [ ] Temporary artifact workflow removed before merge.
- [ ] No production DB write, deploy, question mutation, answer mutation, or secret use.
