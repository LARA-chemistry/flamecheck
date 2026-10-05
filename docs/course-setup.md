(course-setup)=

# Course setup (admin guide)

This chapter walks an admin through setting up a complete course — from the
registration mode to the last time window — and shows how the pieces fit
together. The day-to-day UI tour is in {ref}`Usage <usage>`; the mechanics of
each part are in {ref}`Analyses <analyses>`, {ref}`Multiple choice
<multichoice>` and {ref}`Grading <grading>`.

## The big picture

```{mermaid}
flowchart TD
    subgraph Setup["1 · One-time setup (Admin)"]
        A[Choose registration mode<br/>Settings → Registration] --> B[Create course<br/>name · semester · track]
        B --> C[Configure grading<br/>global default + course override]
        D[Define analysis types<br/>possible ions · max repetitions] --> E[Create analysis instances<br/>answer key · window · label · number]
        F[Design MC cards<br/>questions → cards → sheets] 
        C --> G
        E --> G
        F --> G
    end

    subgraph Enrol["2 · Students join the course"]
        G((course))
        G --> H1[manual:<br/>admin creates members<br/>+ barcodes]
        G --> H2[self-registration:<br/>register + e-mail confirm]
        G --> H3[OAuth:<br/>SSO sign-in +<br/>registration page]
    end

    subgraph Run["3 · The semester runs"]
        H1 --> I
        H2 --> I
        H3 --> I
        I[Assign instances to students<br/>(announcement number)]
        I --> J[Time windows open]
        J --> K{Student submits}
        K -->|analysis| L[auto-graded<br/>per-ion / per-analysis]
        K -->|MC card| M[auto-graded<br/>per course MC points]
        L --> N{wrong + new-analysis mode?}
        N -->|yes| O[fresh re-trial sheet<br/>assistant notified]
        N -->|no| P[counts for course total]
        M --> P
        O --> J
    end

    subgraph Result["4 · Result"]
        P --> Q[course total = Σ counting sheets<br/>− retry deductions + MC points]
        Q --> R{total ≥ passing score?}
        R -->|yes| S[course passed]
        R -->|no| T[course not passed]
        Q --> U[assistant: statistics,<br/>CSV audit export]
    end
```

## Step 1 — Choose how students join

**Settings → Registration** picks exactly one mode (see
{ref}`Registration & authentication <registration>` for the details):

| Mode | Choose it when … |
|------|------------------|
| `manual` | you create every student account yourself (small classes, you have the enrolment list). |
| `self_registration` | students register themselves and confirm their e-mail (you need working e-mail delivery). |
| `oauth` | students have a university SSO (Keycloak / OpenID Connect) and you want zero password management. |

The mode only affects **students**. Assistants and admins always sign in with
a password created by you.

## Step 2 — Create the course

**Courses → New Course**: name (unique), semester (e.g. `WS 2026`), track
(e.g. `biology`), *active*, and the **Notify student** switch (send the
student a PGP-encrypted e-mail confirmation for every submission — only works
when {ref}`ALLOW_EMAILS is enabled <deployment>` and the PGP keys are
configured).

The currently *active course* is selected in **Settings → Application
settings** — it is the course new students default to and the one the demo
seeder treats as the showcase.

## Step 3 — Configure grading

1. Set the **global default** in **Settings → Default grading configuration**:
   grading mode, points, penalties, submission workflow, submission limit,
   final-score strategy, pass mark, MC points/penalty.
2. For each course that deviates, open **Courses → (course) → Grading** and
   save its own configuration — the course row then *overrides* the global
   default for everything (all fields are copied; there is no per-field
   inheritance).

Worked examples for every field are in {ref}`Grading <grading>`.

## Step 4 — Define the analysis programme

1. **Analysis Types** — one entry per *kind* of analysis (e.g. "Practice
   Analysis (1 salt)", "Analysis 3 (full cation scope)"). For each type pick
   the **possible ion set** (the ions that may appear), an optional
   description, the **default time window**, and — for the *new analysis*
   workflow — **max repetitions**.
2. **Analysis instances** — per course, create the concrete sheets: choose
   the type, the **correct answer key** (a subset of the possible ions,
   ideally built from the actual salts you prepared), the **window start/end**,
   the **announcement number** (1st/2nd/… analysis) and a **label**
   (e.g. `Cations1_1`). The substance overview (assistant planning) can
   optionally list the assigned substances per sheet.
3. **Assignments** — assign each instance to the students of the course. In
   the per-student sheet design (the demo's Geology course), every student
   gets their own instance; in a shared-sheet design, many students share one
   instance.

> **Tip:** the demo seed (`manage.py seed_demo --reset`) builds a complete,
> realistic example of all of this — five courses, twelve types, per-student
> sheets with labels and windows spanning all four states — which is a good
> starting point to inspect before configuring your own semester.

## Step 5 — Add multiple-choice cards (optional)

In the **Multiple Choice** page (per course): create the **questions** (with
options, one correct each, plus your documentation notes), group up to three
into a **card** (e.g. "Flame test"), then present it as a time-windowed
**sheet** and assign it to the students. The MC points/penalty live on the
course's grading configuration. See {ref}`Multiple choice <multichoice>`.

## Step 6 — Enrol students & hand out barcodes

- **manual mode**: **Courses → Members → Add** creates the student account
  (username, first/last name, e-mail, `labspace_id`, auto-generated password
  shown once) and can generate the **barcode** at the same time. Print the
  barcodes for the lab.
- **self-registration**: students register at the login page; watch the course
  member list for new accounts.
- **OAuth**: students sign in via the provider; the first sign-in lands on the
  registration page where they pick *your course*.

Assistant accounts are created the same way (Members → role *assistant*); each
assistant only sees the courses you linked them to.

## Step 7 — Open the windows & run the semester

Time windows are set per instance/sheet (and can be changed at any time before
a submission arrives — already submitted sheets are unaffected). During the
semester:

- the **assistant** watches the roster (live window states, per-student
  scores), answers **re-trial notifications** (new-analysis mode), plans lab
  preparation with the **substance overview**, and exports the **CSV audit**
  at the end;
- optionally, submission **e-mail confirmations** go to students (course
  switch) and assistants (Settings → Notifications) — see
  {ref}`Deployment <deployment>` for the `ALLOW_EMAILS` gate and the PGP setup.

## Step 8 — Collect the results

The student's **course result** shows the total (counting analyses + MC cards,
minus re-trial deductions) against the **pass mark**. The assistant dashboard
shows the same per student, and the CSV export carries the full audit trail
(every attempt, score, penalty, timestamp).

## Checklist

- [ ] Registration mode chosen (and e-mail delivery / Keycloak realm working, if used)
- [ ] Course created (+ active course set in Settings)
- [ ] Grading configured (global default; per-course overrides where needed)
- [ ] Analysis types with possible ion sets defined
- [ ] Instances with answer keys, windows, numbers, labels created
- [ ] Instances assigned to students (per-student or shared sheets)
- [ ] MC questions → cards → sheets → assignments (if used)
- [ ] Students enrolled; barcodes printed
- [ ] Assistant(s) linked to the course
- [ ] (optional) `ALLOW_EMAILS` + SMTP/PGP configured for e-mail confirmations
- [ ] (optional) database backup enabled (Settings → Database, SQLite)

## See also

- {ref}`Usage <usage>` — what each role sees day to day.
- {ref}`Grading <grading>` — the scoring fields with worked examples.
- {ref}`Registration & authentication <registration>` — modes, OAuth setup, tokens.
- {ref}`Deployment <deployment>` — running the instance the course lives on.
