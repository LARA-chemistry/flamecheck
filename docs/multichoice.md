(multichoice)=

# Multiple choice

Besides the ion analyses, a course can contain **multiple-choice cards**:
small, self-contained question sets (e.g. "which flame colour does potassium
give?", or a binary all-or-nothing pharmacopoeia monograph) that students
answer on a **time-windowed sheet** and that are graded by the course's
multiple-choice settings.

## The building blocks

| Concept | Model | What it is |
|---------|-------|------------|
| **Question** | `MCQuestion` | One question of a course: the statement text, a *description* and *remarks* (free text for the admin's own documentation), and its options. |
| **Option** | `MCOption` | One answer option of a question: text, a `sort_order` for display, and the `is_correct` flag. Exactly one option per question is correct. |
| **Card** | `MCCard` | A titled group of **up to three questions** (e.g. "Flame test", "EP monograph"). The card is the unit the student sees and the unit that is graded as a whole. |
| **Sheet** | `MCSheet` | A *concrete presentation* of a card to a course: card + course + **time window** (`window_start`/`window_end`) + announcement `number`. Like analysis instances, sheets are the per-course, time-gated objects. |
| **Assignment** | `MCStudentAssignment` | Links a sheet to one student (with a per-student number). |
| **Submission** | `MCSubmission` | Immutable and timestamped: the answers as a JSON object (question id → option id), the `submission_number`, an `idempotency_key`, and the graded result. |

Questions and cards are **per course**, so two courses can reuse the same
question *text* with different options — or, more typically, each course keeps
its own set. A sheet always belongs to exactly one card and one course.

## Time windows

Sheets have the same window states as analyses — `open`, `too early`,
`too late`, `submitted` (see {ref}`Analyses <analyses>`). On the student's home
page the cards are listed below the analyses, each with its own window. A
sheet can be submitted multiple times (e.g. after a correction); which
submission counts for the course total is decided by the course's
`final_score_strategy` (best, default, or last) — exactly like analyses.

## Grading

Multiple choice is configured on the course's {ref}`grading configuration <grading>`
by two fields:

| Field | Default | Meaning |
|-------|---------|---------|
| `mc_points_per_card` | 10 | Points for a card when **every** question is answered correctly. |
| `mc_penalty_per_wrong` | 2 | Points deducted for **each** wrongly answered question. |

The score of one submission is:

```
score = max(0, mc_points_per_card − mc_penalty_per_wrong × wrong_count)
```

with `ideal_score = mc_points_per_card`. Every question must be answered (a
missing answer is a validation error, not a wrong answer).

### Example 1: flame-test card

A Chemistry course configures `mc_points_per_card = 10`,
`mc_penalty_per_wrong = 2`. The card "Flame test" has three questions:

| # | Question | Correct option |
|---|----------|----------------|
| 1 | Which flame colour does **Na⁺¹** give? | yellow |
| 2 | Which flame colour does **K⁺¹** give? | lilac (through cobalt glass) |
| 3 | Which flame colour does **Ca²⁺** give? | brick red |

| Student answers | wrong | Score |
|-----------------|-------|-------|
| yellow / lilac / brick red | 0 | **10** |
| yellow / lilac / *green* | 1 | 10 − 2×1 = **8** |
| *orange* / *white* / brick red | 2 | 10 − 2×2 = **6** |
| *orange* / *white* / *green* | 3 | 10 − 2×3 = **4** |

### Example 2: all-or-nothing monograph card

The Geology demo course uses an **EP (European Pharmacopoeia) monograph** card
with three binary sub-questions (yes/no). With `mc_points_per_card = 10` and a
high `mc_penalty_per_wrong` (or simply a wrong answer), the card effectively
behaves all-or-nothing: a single wrong sub-test costs the bulk of the card's
points — matching the "the monograph is only compliant if *all* tests pass"
lab rule.

## Managing multiple choice (admin)

The admin's **Multiple Choice** page is the per-course designer:

1. **Questions** — create questions with options (mark the correct one), plus
   description/remarks for your own documentation.
2. **Cards** — group up to three questions into a titled card.
3. **Sheets** — present a card as a time-windowed sheet to the course (choose
   the window and announcement number) and assign it to the selected students.
4. **Grading** — set `mc_points_per_card` and `mc_penalty_per_wrong` on the
   course's grading configuration (see {ref}`Grading <grading>`).

The sheet's window and the assignment flow work exactly like the analysis
instances, so the same admin muscle memory applies.

## See also

- {ref}`Grading <grading>` — the scoring fields and their per-course overrides.
- {ref}`Analyses <analyses>` — the ion-analysis counterpart (windows, states, totals).
- {ref}`Course setup <course-setup>` — where the MC cards fit into a semester plan.
