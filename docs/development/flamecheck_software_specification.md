# Software Specification: Inorganic Analysis Submission System

## 1. Overview

**Purpose:** A web-based system for first-semester chemistry students to submit inorganic qualitative analysis results. Students authenticate with a personal barcode, view the cations/anions possible for their assigned analysis, and tick the ions they believe are present. The system automatically scores submissions (10 points per correctly identified analysis).

**Inspiration from the attached document:** The provided "Ansagemodus" document describes an analogue process: a student scans a barcode from their analysis sheet at an announcement computer at the assistant's desk, the system shows which ions can occur, the student checks off ("Ankreuzen") the ions found and finishes the announcement, then a control query ("Kontrollabfrage") reveals the result. Several announcements (e.g., 3rd and 4th analysis) are possible, each subject to a **date/time window** ("Datum des Ansagezeitraumes beachten" – too early/too late submissions are rejected), ending in a final result and point allocation [1]. The web system replaces the desk computer and barcode scanner with browser-based barcode scanning while preserving this workflow.
S

## 2. User Roles

| Role | Capabilities |
|---|---|
| **Student** | Login via personal barcode, view assigned analyses within the valid time window, submit ion selections, view results and points |
| **Assistant (Assistent)** | Manage analysis sheets/barcodes, view submitted results per group, support students during announcement time |
| **Admin** | Manage users/barcodes, define analyses with their ion sets, set points per correct analysis (default 10), configure the number of analyses per course, set announcement time windows, view statistics |

## 3. Functional Requirements

### 3.1 Student Workflow
1. **Login:** Student scans their personal barcode (via webcam of smartphone/USB scanner through a browser barcode-scanning library, e.g. `html5-qrcode` or `@zxing/browser`) [1]. The barcode resolves to the student's identity and their assigned analysis sheet.
              - alternatively, a student logs in via a username/password or institutional SSO (e.g., Shibboleth) if barcode scanning is unavailable.
2. **Time-window check:** The system validates the current date/time against the announcement window for the analysis. Submissions are rejected if too early or too late (as in "zu früh!"/"zu spät!" [1]).
3. **Analysis display:** Depending on the assigned analysis, the form shows **all possible cations and anions** for that analysis (not the correct ones) [1].
4. **Submission:** Student ticks the ions they believe are present and confirms ("Submit") [1]. A second confirmation dialog ensures they are ready to submit, as submissions are final and cannot be edited.
5. **Control query & result:** Immediately after submission, the system reveals which ions were correct and awards **10 points per correctly identified analysis** [1].
                            - optionally, the system can deduct points for false positives if configured by the admin.
6. **Multiple announcements:** A student may perform several analyses (e.g., 3rd, 4th analysis) within the allowed window; each is scored independently and accumulated into the final result and point allocation [1].
7. **Final result:** After all assigned analyses, the student sees the total points and the ideal result ("Das Idealergebnis") [1].

### 3.2 Admin Configuration
- **Ion catalog:** Master list of all cations (e.g. Group I–IV/V: Na⁺, K⁺, NH₄⁺, Mg²⁺, Ca²⁺, Ba²⁺, Cu²⁺, Fe²⁺/Fe³⁺, Al³⁺, Zn²⁺, Mn²⁺, etc.) and anions (Cl⁻, Br⁻, I⁻, SO₄²⁻, SO₃²⁻, CO₃²⁻, PO₄³⁻, NO₃⁻, NO₂⁻, S²⁻, etc.).
- **Substance catalog:** Optional mapping of ions to common salts (e.g., NaCl, KBr, CuSO₄) for reference.
- **Analysis definition:** Each analysis type defines (a) the **set of possible ions** shown to students, and (b) the **correct answer set** per concrete analysis instance (e.g., "Analysis 12: contains NH₄⁺, SO₄²⁻, Cu²⁺").
- **Points per correct analysis:** Admin-adjustable, default **10** [1].
- **Number of analyses per course/semester:** Admin-adjustable (e.g., 2, 3, 4 announcements per student) [1].
- **Time windows:** Per-analysis start/end date and time for submissions.
- **Barcodes:** Generate and assign unique barcodes (Code128 or QR) to students/analysis sheets.

### 3.3 Grading Logic
- **Per-ion mode (default, as described):** 10 points per correctly identified ion; optionally configurable to deduct points for false positives.
- **Per-analysis mode (alternative, admin-selectable):** 10 points only if the full ion set is exactly correct.
- Results are final upon submission (no editing), consistent with the "Kontrollabfrage → Ergebnis" flow [1].

## 4. Technical Architecture

### 4.1 Backend — Django
- **Django 6.x + django Ninja** REST API.
- **SQLite** or **PostgreSQL** database. (.env config for DB connection)
- **Authentication:** Token-based (JWT) for API; session cookie for web frontend. Django allauth for login (students, assistants, admins), shibboleth for institutional authentication.
- **Models (core):**
  - `User` (extends Django user; role: student/assistant/admin), `StudentBarcode` (unique barcode value, FK student)
  - `Ion` (name, symbol, charge, type: cation/anion, group)
  - `AnalysisType` (name, list of possible ions)
  - `AnalysisInstance` (FK AnalysisType, FK assigned student, correct ion set, time window start/end, status, score)
  - `Submission` (FK AnalysisInstance, selected ions M2M, timestamp, score, auto-graded)
  - `Config` (points per correct analysis, analyses per course, active course)
- **API endpoints:**
  - `POST /api/auth/scan/` → validates barcode, returns session + student's analyses
  - `GET /api/analyses/` → list analyses for logged-in student with time-window status
  - `POST /api/analyses/{id}/submit/` → submits ion selection, grades, returns result
  - `GET /api/analyses/{id}/result/` → detailed correct/incorrect ions
  - `GET /api/me/summary/` → final result and total points
  - `GET /api/analyses/{id}/substances/` → list of substances related to the analysis
  - `GET /api/analyses/{id}/substances/{substance_id}/` → details of a specific substance
  - Admin: CRUD under `/api/admin/…` (ions, analyses, students, barcodes, config, time windows)
- **Barcode verification** is server-side (barcode → DB lookup), never trust client.
- **Security:** - HTTPS, hashed credentials, rate-limiting on submission endpoint, one-time barcode per analysis window. 
                - save docker environment - safety hardend (e.g., no root, non-default ports, firewall rules).
                - Intrusion possiblities minimized by using Django's built-in security features (CSRF, XSS protection, etc.).
                - extra hardening: Docker container isolation, minimal base images, regular security updates.
                - prevent brute-force attacks: rate limiting, account lockout after multiple failed attempts, CAPTCHA for repeated failed logins.
                - prevent student hacking: barcodes are unique per student and analysis, submissions are timestamped and immutable, and the system logs all actions for audit purposes.

### 4.2 Frontend — Vue 3 + Vite
- **Vue 3** (Composition API, `<script setup>`), **Vite**, **Pinia** for state, **Vue Router**. Use latest viete technologies for fast development and hot module replacement.
- **UI library:** Naive UI or PrimeVue (modern, form/checkbox components).
- **Barcode scanning:** `@zxing/library` or `html5-qrcode` — supports both webcam scanning and USB keyboard-wedge barcode scanners (which act as fast keystroke input ending in Enter).
- **Key views:**
  1. `LoginView` – barcode scan (webcam viewfinder + fallback USB/keyboard input)
  2. `AnalysisListView` – assigned analyses with time-window status (open / too early / too late / submitted)
  3. `SubmissionFormView` – two-column checkbox form (cations | anions), confirm button, submission deadline countdown
  4. `ResultView` – control-query style feedback: ticked ions highlighted green (correct) / red (wrong), missing correct ions shown, points earned
  5. `SummaryView` – all analyses, total points, ideal result comparison
  6. `AdminDashboard` (separate route) – ion/analysis/student management, time windows, points config, submission statistics
- **Responsive** design for laptop/tablet use at lab desks.


### 4.4 Testing
- **Backend:** Pytest for unit tests (models, API endpoints), coverage reports.
- **Frontend:** Vitest + Vue Test Utils for component/unit tests, Cypress for end-to-end testing (login, submission, result display).
- **Integration tests:** Docker Compose environment with test database, simulating student submissions and admin actions.

### 4.3 Deployment
- Nginx serving built Vue assets + proxying API to Django (Gunicorn).
- PostgreSQL database.
- Docker Compose setup (web, api, db) for easy lab-room deployment.

## 5. Non-Functional Requirements
- **Availability during announcement windows:** System must be up and fast (< 2 s response) during peak submission time.
- **Concurrent users:** Support 30–60 students submitting within a short window.
- **Audit:** All submissions timestamped and immutable; admin can export results as CSV.
- **Security:** HTTPS, hashed credentials, barcode as one-time-scannable token per window, rate-limiting on submission endpoint.
- **Privacy:** Student data minimal (name, matriculation number, lab, labspace-id, barcode, scores).

## 6. Data Model Sketch

```
Student (id, name, matriculation_no, barcode, role)
Ion (id, symbol, name, charge, kind: cation|anion, group)
AnalysisType (id, name, possible_ions M2M[Ion])
AnalysisInstance (id, type FK, student FK, correct_ions M2M[Ion],
                  window_start, window_end, status, created_at)
Submission (id, analysis FK, selected_ions M2M[Ion],
            correct_count, wrong_count, score, submitted_at)
Config (points_per_analysis=10, analyses_per_course=3, course_active)
```

## 7. Scoring Example

Analysis 3's correct set: {NH₄⁺, SO₄²⁻, Cu²⁺}. Student ticks {NH₄⁺, SO₄²⁻, Cu²⁺, Zn²⁺} → 3 correct × 10 = **30 points** (false positive Zn²⁺ ignored or penalized per admin config). After 4 analyses, SummaryView shows total points vs. ideal result [1].


