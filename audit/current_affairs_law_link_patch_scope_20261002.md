# Current-affairs law-link patch scope

Branch: `data/current-affairs-law-linkage-v1-20261002`

This patch is deliberately narrow:

- adds a versioned deterministic law/policy-link rule registry;
- adds a fail-closed linker with positive/negative regression examples;
- wires high-confidence inferred laws into current-affairs signal generation;
- recomputes historical relations when a newly supported law is added;
- uses a temporary read-only PR artifact workflow only to rebuild and inspect derived snapshots.

Out of scope:

- production deployment;
- production database changes;
- question/answer mutations;
- student-auth changes;
- external paid services;
- broad category-to-law guessing;
- claiming that a related law was amended.
