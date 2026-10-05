(analyses)=

# Analyses

An **analysis** in FlameCheck is a qualitative ion determination: the student
is shown a set of *possible* cations and anions and must select exactly those
that are present in their (secret) sample. This chapter explains the building
blocks — types, instances, assignments — the time-window mechanism, the two
submission workflows, and how the course total is assembled.

## The building blocks

| Concept | Model | What it is |
|---------|-------|------------|
| **Analysis type** | `AnalysisType` | A user-defined analysis *catalog entry*: a name (e.g. "Analysis 3"), a description shown to students, the **possible ion set** (the union of cations/anions that may appear), optional **default time window**, and — for the *new analysis* workflow — the **maximum repetitions** (`max_repetitions`). |
| **Analysis instance** | `AnalysisInstance` | A *concrete sheet*: one instance of a type with a **course link**, the **correct answer key** (a subset of the type's possible ions), optionally **assigned substances** (for the substance overview), a **time window** (`window_start` / `window_end`), an **announcement number** (`number`, e.g. 3 = "3rd analysis of the course") and a human-readable **label** (e.g. `Cations1_2`). |
| **Assignment** | `StudentAssignment` | Links an instance to one student of a course, with the announcement number. There is deliberately *no* uniqueness on (course, student, number) — a student can receive several sheets for the same announcement (the re-trial workflow). |
| **Submission** | `Submission` | An immutable, timestamped record: the selected ions, the 1-based `submission_number`, a client-generated `idempotency_key`, and the graded result (score, correct/wrong/missing counts, penalty). |

**Per-student sheets.** Every student gets their *own* instance (with their
own answer key and label), so two students in the same course can have
different salts even for the "same" analysis. The demo seed labels them
`<type name, no spaces>_<labspace id>` (e.g. `Analysis1_2`), but any label is
possible.

## Time windows & states

Every instance (and every multiple-choice sheet) has a **submission window**:
the earliest and latest moment a submission is accepted (both inclusive,
UTC). The UI derives a live state:

| State | Meaning |
|-------|---------|
| `open` | The window is currently active — the student can submit. |
| `too early` | The window has not started yet (the student sees the analysis but cannot submit). |
| `too late` | The window has closed (the result is shown once it exists). |
| `submitted` | The student already has a (counting) submission for this sheet. |

```{mermaid}
stateDiagram-v2
    [*] --> too_early
    too_early --> open : window_start reached
    open --> submitted : student submits
    open --> too_late : window_end passed
    submitted --> too_late : window_end passed
    too_late --> [*]
```

Submissions outside the window are rejected server-side (a student who opens
the analysis a minute too late gets a clear error, not a stored submission).
The *announcement number* plus the label is what the assistant and the student
see, so "3rd analysis" stays meaningful across re-trials.

## The two submission workflows

The course's {ref}`grading configuration <grading>` decides what happens after a
submission — and, in particular, after a *wrong* one.

### Workflow 1: resubmit (default)

The student keeps the same sheet and may submit again, up to
`max_submissions_per_analysis` attempts (default 3). In *per-ion* mode each
later attempt is penalised by the retry penalties (default −2 for the 2nd, −4
for the 3rd); in *per-analysis* mode the penalties turn a correct-but-late
answer into 10 → 8 → 6 (see the {ref}`worked examples <grading>`). The final
score of the sheet is the **best** (default) or the **last** submission,
according to `final_score_strategy`.

### Workflow 2: new analysis (re-trial)

When `submission_mode = new_analysis`, a *wrong* submission (selected set ≠
answer key) does **not** allow another attempt on the same sheet. Instead the
system:

1. checks that the student has not yet exhausted the analysis type's
   `max_repetitions` for this (course, announcement number),
2. composes a **fresh random instance of the same type** (a random subset of
   its possible ions), inheriting the original window and announcement number,
3. assigns it to the student, and
4. raises an **analysis notification** so the course's assistants see that a
   re-trial was handed out.

For the **course total**, only the *newest* instance of each announcement
number counts; every earlier (superseded) re-trial subtracts the course's
`retry_point_deduction` from the total (see {ref}`Course total <grading-course-total>`).

```{mermaid}
flowchart TD
    A[Student submits sheet #3] --> B{Correct?}
    B -- yes --> C[Score recorded,<br/>sheet done]
    B -- no --> D{submission mode?}
    D -- resubmit --> E[Same sheet stays open<br/>next attempt is penalised]
    D -- new analysis --> F{max_repetitions<br/>exhausted?}
    F -- no --> G[Fresh random sheet #3b<br/>assistant notified]
    F -- yes --> H[Sheet closed<br/>0 points for this announcement]
    G --> A
```

## Example: a semester programme

A typical course (like the Geology demo course) combines several announcement
numbers:

| Announcement | Type | Possible ions | Window | Grading |
|--------------|------|---------------|--------|---------|
| 1 | Practice Analysis (1 salt) | cations Na⁺¹ K⁺¹ NH₄⁺¹ · anions Cl⁻¹ SO₄²⁻ NO₃⁻¹ | week 1 | per-analysis, 10 pts, −2/−4 retry |
| 2 | Analysis 1 (2 salts) | same scope | week 2 | per-analysis |
| 3 | Analysis 2 (max. 3 salts) | + Li⁺¹ Ba²⁺ Mg²⁺ Ca²⁺ / + CO₃²⁻ | week 3 | per-analysis, 3 attempts |
| 4–5 | Analysis 3–4 (full cation scope) | cations only | weeks 4–5 | per-analysis |
| – | EP monograph MC card | 3 binary questions | week 5 | 10 pts all-or-nothing |

Each student's sheet for announcement *n* is a per-student instance (own salts,
own label, e.g. `Analysis3_2`), and the pass mark for the course might be
30 points across all analyses + cards.

## Example: the "new analysis" workflow in numbers

Chemistry demo course, `submission_mode = new_analysis`, `retry_point_deduction = 5`,
`max_repetitions = 2`, 10 points per correct analysis:

1. **Sheet A** (announcement 2, random 2-salt composition) — student answers
   wrong → 0 points, sheet closed.
2. **Sheet B** (fresh random composition, same announcement) — student answers
   correctly → 10 points.
3. Course total: the newest sheet (B, 10 pts) counts, and the one superseded
   sheet (A) subtracts the 5-point retry deduction → **5 points** for
   announcement 2.

Had the student also exhausted their re-trials on B (wrong again), announcement
2 would contribute `10 − 2×5 = 0` (the total is floored at 0).

## See also

- {ref}`Grading <grading>` — every scoring field and worked examples.
- {ref}`Multiple choice <multichoice>` — the card-based tasks that sit beside the analyses.
- {ref}`Course setup <course-setup>` — how an admin builds all of this.
- [Architecture](development/architecture.md#6-the-submission-lifecycle-core-business-flow) —
  the submission lifecycle, idempotency and concurrency details.
