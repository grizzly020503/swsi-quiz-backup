# Approved 104-1 direct-service source release

Owner approved the exact original-PDF comparison with 「是 繼續」. PR #598 head `ed45ba6c7c1ecbbbf305bb0df96cad457ef9135e` passed 19 checks (one unrelated push-only feed job skipped). Merged as `7284dc203f8c87d29f5eb50a825d19d02f8d769b`.

The bounded production transaction was rehearsed with ROLLBACK, original hashes re-read and matched, then executed with COMMIT after CI. Its assertions compare all 37 columns of each target postimage, all 4,797 unrelated full rows, and the complete AI scheduler configuration. Only approved source text fields were assigned; answers, grading and scheduler state remain unchanged. The source-change trigger clears stale AI enrichment to pending. A separate post-commit SELECT confirmed:

| ID | Answer | Full PostgreSQL JSONB SHA-256 |
|---|---|---|
| DS-104-1-22 | A | 02a3533a3069def3a66a95b7f0a69b2a0f39412046109ee8059bd2f1c521516b |
| DS-104-1-27 | B | 3df93fa3f207087290a50d22f76a55d467d36342c046aa5c23dedd1ebb635913 |
| DS-104-1-29 | D | 9128e3a723e42428587eb027f3f6314c899af3c29e1326663489ef374dec11c8 |

Corpus revision: `165abd809ec22cf69379`; 4,800 MCQs and 240 essays. The follow-up unhold change requires all three exact production postimages. Browser tests cover approved practice/mock scoring, preserved due-review progress, offline availability, and a separate synthetic quarantine fixture. Whole-platform closure and private recovery/model acceptance are not asserted by this source release.
