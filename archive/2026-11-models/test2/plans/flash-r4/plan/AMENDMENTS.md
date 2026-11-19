# Owner split-rule amendments

This is a copy of `plan/`; the original is unchanged. Only the rule for jobs longer than 8 hours is amended. Split into 8-hour parts plus remainder; book each part independently on a later workday using the booking rule. Prefer the first part's cleaners when free; use other free cleaners when not. Each part remains subject to the existing workday, spacing and 90-day rules; a failed part leaves the whole booking unchanged. The other plan decisions, including job-as-unit extension cascades, stand.

| Copied file | Split-rule change |
|---|---|
| `spec.md` | US1 narrative, 10-hour acceptance case, FR-005 and Job entity: independent later-workday parts and replacement cleaners when needed. |
| `data-model.md` | Job parts, JobPart days/assignments, Assignment cleaner IDs and cross-entity invariant permit different cleaners and nonconsecutive later workdays; invoice lines include the distinct cleaners across all parts. |
| `research.md` | R3 scans each part independently with preferred first-part cleaners or replacements; removes the rejected alternative that forbade changing cleaners; R4 preserves job-as-unit cascades while applying the per-part rule. |
| `contracts/desktop-api.md` | POST booking description uses independent later-workday parts and preferred/replacement cleaners. |
| `contracts/mobile-logic.md` | `bookJob` description and 10-hour golden vector use the amended split rule. |
| `tasks.md` | Shared rule, cascade description, US1 tests/implementation T014/T015/T018/T020 and extension tests/implementation T033/T035 now use the amended rule. |
| `quickstart.md` | Mobile expected vectors and desktop booking walkthrough reflect independent later-workday booking and cleaner replacements. |

No other copied plan files were changed.
