# FlameCheck documentation

**FlameCheck** is a web-based submission system for inorganic qualitative
analysis. Students authenticate with their university login (or a personal
barcode), submit their ion-analysis results and multiple-choice cards within
time-gated windows, and are graded automatically. Assistants monitor progress
per course; admins configure courses, analyses, grading and authentication.

```{figure} _static/flamecheck_logo.svg
:alt: The FlameCheck logo — a Bunsen-burner flame with a checkmark
:width: 120px
```

## Feature overview

- **Ion analyses** — user-defined analysis types, per-student sheets, time
  windows (`open` / `too early` / `too late` / `submitted`), immutable
  timestamped submissions with idempotency keys.
- **Two scoring modes** — *per ion* or *per analysis* (all-or-nothing), with
  retry penalties, false-positive deductions and a configurable final-score
  strategy; a global default plus optional **per-course overrides**.
- **Two submission workflows** — *resubmit* the same sheet, or a *new
  analysis* re-trial (a fresh random composition of the same type) when the
  first attempt is wrong.
- **Multiple-choice cards** — questions grouped into cards (up to three
  questions), presented as time-windowed sheets and graded per course.
- **Flexible registration & authentication** — password, barcode,
  self-registration with e-mail confirmation, or OAuth / OpenID Connect
  (Keycloak); JWT access + refresh tokens with revocation.
- **PGP-encrypted and signed e-mail notifications** for submissions, gated by
  the `ALLOW_EMAILS` environment variable.
- **Runs anywhere** — SQLite by default, PostgreSQL optional; Docker compose
  files for production, staging and development.

```{toctree}
:maxdepth: 1
:caption: Getting started

installation
usage
```

```{toctree}
:maxdepth: 1
:caption: The application (user guide)

analyses
multichoice
grading
registration
```

```{toctree}
:maxdepth: 1
:caption: For admins & DevOps

course-setup
deployment
```

```{toctree}
:maxdepth: 1
:caption: Project info

changelog
contributing
```

```{toctree}
:maxdepth: 1
:caption: Specifications & developer docs

development/ion_symbol_convention
development/flamecheck_software_specification
development/architecture
```

```{toctree}
:maxdepth: 2
:caption: API reference

flamecheck
```
