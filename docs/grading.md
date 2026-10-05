(grading)=

# Grading configuration

Grading is controlled by the **GradingConfig** — one *global default* row plus
at most one *overriding* row per course. When an analysis or card is graded,
FlameCheck uses the course's own configuration if it exists, otherwise the
global default (`GradingConfig.get_for_course`). This is what lets a single
installation run, say, a strict per-analysis Geology course next to a
forgiving per-ion Biology course.

## The fields

| Field | Default | Applies to | Meaning |
|-------|---------|------------|---------|
| `grading_mode` | `per_ion` | analyses | `per_ion` — points per correctly identified ion. `per_analysis` — **all-or-nothing**: full points only when the selected ion set is exactly the answer key. |
| `points_per_correct_ion` | 10 | analyses | In per-ion mode: points per correct ion. In per-analysis mode: the points for a completed (exact) analysis. |
| `penalty_second_submission` | 2 | analyses | Points deducted from the **2nd** submission (retry penalty). |
| `penalty_third_submission` | 4 | analyses | Points deducted from the **3rd** (and later) submission. |
| `false_positive_deduction` | 0 | per-ion mode | Points deducted **per wrongly selected** ion (0 disables). |
| `submission_mode` | `resubmit` | analyses | `resubmit` — retry the same sheet. `new_analysis` — a wrong answer hands out a fresh random analysis of the same type (up to the type's `max_repetitions`). |
| `retry_point_deduction` | 0 | new-analysis mode | Points subtracted from the **course total** for each earlier (superseded) re-trial attempt. |
| `max_submissions_per_analysis` | 3 | resubmit mode | Maximum number of submissions per analysis instance. |
| `final_score_strategy` | `best` | analyses + MC | When a sheet has several submissions, which one counts: `best` (highest score) or `last` (most recent). |
| `passing_score` | 50 | course | Minimum total points across all analyses *and* cards to pass the course (0 disables the pass check). |
| `mc_points_per_card` | 10 | MC | Points per fully correct card. |
| `mc_penalty_per_wrong` | 2 | MC | Points deducted per wrongly answered question on a card. |

**Where to configure:** the global default lives in **Admin → Settings →
Default grading configuration** (and in the Django admin), each course's
override in the **grading card of the Courses view** (Admin → Courses →
course → Grading). Per-course overrides win over the global default.

## Per-ion mode (default)

Every correctly selected ion is worth `points_per_correct_ion`; wrong
selections deduct `false_positive_deduction` each; a 2nd/3rd submission deducts
the retry penalty. The score is floored at 0.

```
score = max(0, correct × points − wrong × false_positive − penalty(submission_number))
```

### Worked example

`points_per_correct_ion = 10`, `false_positive_deduction = 1`,
`penalty_second_submission = 2`, answer key = {Na⁺¹, K⁺¹, Cl⁻¹} (3 ions, ideal
score 30):

| Attempt | Student selects | correct | wrong | missing | penalty | Score |
|---------|-----------------|---------|-------|---------|---------|-------|
| 1st | Na⁺¹, K⁺¹ | 2 | 0 | 1 | 0 | **20** |
| 2nd | Na⁺¹, K⁺¹, Cl⁻¹, Mg²⁺ | 3 | 1 | 0 | 2 | 30 − 1 − 2 = **27** |

With `final_score_strategy = best`, the sheet's final score is **27** (the
2nd attempt). With `last`, it would be 27 as well here — but a *worse* final
attempt would count in that case.

## Per-analysis mode (all-or-nothing)

The submission either matches the answer key **exactly** (and earns the full
`points_per_correct_ion` value, minus the retry penalty) or scores **0**.
Partial credit does not exist.

```
score = (selected == key) ? max(0, points − penalty(submission_number)) : 0
```

### Worked example (the Geology demo course)

`points_per_correct_ion = 10`, `penalty_second_submission = 2`,
`penalty_third_submission = 4`, `max_submissions_per_analysis = 3`:

| Attempt | Result | Score |
|---------|--------|-------|
| 1st | exact match | **10** |
| 1st wrong → 2nd exact | penalty −2 | **8** |
| 1st wrong → 2nd wrong → 3rd exact | penalty −4 | **6** |
| 3 wrong attempts | — | **0** |

This is the classic "all salts correct or nothing" scheme: a student who
identifies 11 of 12 ions gets 0, but gets the full 10 on the corrected 2nd
attempt (minus the 2-point retry penalty).

## Submission workflows & the course total

### resubmit

Each announcement number contributes the final score of its single sheet
(best or last submission, per `final_score_strategy`).

(grading-course-total)=

### new analysis (re-trial)

One announcement number can accumulate **several sheets** (one per re-trial).
Only the **newest** sheet of each announcement counts toward the total; every
earlier, superseded sheet subtracts `retry_point_deduction`:

```
total = max(0, Σ score(newest sheet per announcement) − retry_point_deduction × superseded_sheets)
```

### Example

`retry_point_deduction = 5`, 10 points per correct analysis:

| Announcement | Sheets (in order) | Scores | Counting sheet | Superseded | Contribution |
|--------------|-------------------|--------|----------------|------------|--------------|
| 1 | A1 | 10 | A1 (10) | 0 | 10 |
| 2 | A2 → B2 | 0, 10 | B2 (10) | 1 (A2) | 10 − 5 = 5 |
| 3 | A3 → B3 | 0, 0 | B3 (0) | 1 (A3) | 0 − 5 = −5 → floored |

Course total = max(0, 10 + 5 − 5) = **10**.

## Multiple choice

MC cards are graded per submission:

```
score = max(0, mc_points_per_card − mc_penalty_per_wrong × wrong_count)
```

and the sheet's final score follows `final_score_strategy` (best/last), exactly
like analyses. MC points are added to the course total next to the analysis
points, and both are compared against `passing_score`.

### Worked example

`mc_points_per_card = 10`, `mc_penalty_per_wrong = 2`, a 3-question card:
all correct → **10**; one wrong → **8**; three wrong → **4**.

## The pass mark

`passing_score` (default 50; 0 disables the check) is the minimum *total*
points a student needs across all counting analyses **and** cards to pass the
course. The student's course result shows `total_score`, `ideal_score`,
`passing_score` and a `passed` flag; the assistant dashboard and CSV export
surface the same numbers per course.

## Which configuration applies — quick reference

```
for a sheet of course C:
    config = C.own GradingConfig  if it exists
           else  the global default GradingConfig
```

- A **new course** automatically inherits the global default — set the default
  sensibly, then override per course where the lab rules differ.
- Changing the global default does **not** alter courses that have their own
  row.
- Grading of an *existing* submission is fixed at submit time (the stored
  score is immutable); a later config change affects only new submissions and
  the derived totals.

## See also

- {ref}`Analyses <analyses>` — time windows and the submission workflows.
- {ref}`Multiple choice <multichoice>` — the MC building blocks.
- {ref}`Course setup <course-setup>` — configuring a semester end to end.
