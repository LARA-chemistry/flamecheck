"""
End-to-end verification of the full FlameCheck app against the example dataset.

Usage (server must be running and the example dataset loaded):

    uv run python manage.py migrate
    uv run python manage.py load_examples --reset
    uv run python manage.py runserver           # default: http://127.0.0.1:8000
    uv run python examples/verify_demo.py       # in a second terminal

The script exercises the whole stack over real HTTP: the built frontend
(index + static assets), authentication (password, barcode, refresh, logout
revocation), the complete student flow (list / detail / substances / submit /
retry / idempotency / window states / limits / result / summary), the seeded
submissions, the assistant views (roster, per-student submissions, CSV
export), the admin API (courses, grading config, app settings) and the
substance catalog plus role-based access control.

Exit code 0 means every check passed.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import uuid
from html.parser import HTMLParser

BASE = "http://127.0.0.1:8000"
API = BASE + "/api/v1"
PASSWORD = "FlameCheck-Demo-123"  # noqa: S105  (intentional shared demo password)

PASS = "\033[32mPASS\033[0m"  # noqa: S105  (ANSI colour code, not a password)
FAIL = "\033[31mFAIL\033[0m"
_results: list[tuple[bool, str, str]] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    """Record and print one verification result."""
    _results.append((condition, name, detail))
    mark = PASS if condition else FAIL
    line = f"[{mark}] {name}"
    if detail and not condition:
        line += f"  -- {detail}"
    print(line)
    return condition


def request(method: str, path: str, token: str | None = None, body: dict | None = None, raw: bool = False):
    """
    Perform an HTTP request; returns (status_code, parsed_json_or_text).

    ``path`` is an absolute URL, the site root ``/``, or an API path.
    """
    if path.startswith("http"):
        url = path
    elif path == "/":
        url = BASE + "/"
    else:
        url = API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)  # noqa: S310  (fixed http://127.0.0.1 BASE)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            payload = resp.read().decode()
            return resp.status, (payload if raw else (json.loads(payload) if payload else None))
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode()
        try:
            return exc.code, (payload if raw else json.loads(payload))
        except json.JSONDecodeError:
            return exc.code, payload
    except urllib.error.URLError as exc:
        return 0, f"connection error: {exc.reason}"


def login(username: str, password: str = PASSWORD) -> tuple[str | None, dict | None]:
    """Log in by password; returns (access_token, response)."""
    status, resp = request("POST", "/auth/login", body={"username": username, "password": password})
    if status != 200 or not isinstance(resp, dict):
        return None, resp
    return resp["tokens"]["access"], resp


def ion_id(ions: list[dict], symbol: str) -> int | None:
    """Find an ion id in a list of ion dicts by symbol."""
    for ion in ions:
        if ion.get("symbol") == symbol:
            return ion["id"]
    return None


class AssetRefParser(HTMLParser):
    """Collects src/href references to /static/ assets from the index page."""

    def __init__(self) -> None:
        super().__init__()
        self.assets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record any src/href that points into /static/."""
        for attr, value in attrs:
            if attr in ("src", "href") and value and value.startswith("/static/"):
                self.assets.append(value)


def verify_frontend() -> None:
    """1. Built frontend: SPA index + all referenced static assets."""
    status, html = request("GET", "/", raw=True)
    check(
        "frontend: GET / serves the built SPA index",
        status == 200 and isinstance(html, str) and 'id="app"' in html,
        f"status={status}",
    )
    if not isinstance(html, str):
        return
    parser = AssetRefParser()
    parser.feed(html)
    check("frontend: index references /static/ assets", len(parser.assets) >= 2, f"assets={parser.assets}")
    for asset in parser.assets[:4]:
        status, body = request("GET", BASE + asset, raw=True)
        ok = status == 200 and isinstance(body, str) and len(body) > 0
        check(f"frontend: {asset} serves", ok, f"status={status}")


def verify_auth() -> str | None:
    """2. Authentication; returns a fresh access token for student-david."""
    access, resp = login("student-david")
    check("auth: password login for student-david", access is not None and isinstance(resp, dict))
    if access is None or not isinstance(resp, dict):
        return None
    check(
        "auth: login payload carries user + analyses",
        resp["user"]["username"] == "student-david" and len(resp["analyses"]) == 4,
    )

    status, _ = request("POST", "/auth/login", body={"username": "student-emma", "password": "wrong-password"})
    check("auth: wrong password rejected (401)", status == 401, f"status={status}")

    status, resp = request("POST", "/auth/barcode/scan", body={"barcode": "FC-DEMO-0004"})
    check(
        "auth: barcode scan login works",
        status == 200 and isinstance(resp, dict) and resp.get("user", {}).get("username") == "student-david",
        f"status={status}",
    )
    status, _ = request("POST", "/auth/barcode/scan", body={"barcode": "FC-DOES-NOT-EXIST"})
    check("auth: unknown barcode rejected (401)", status == 401, f"status={status}")

    # Refresh + logout revocation (disposable user so david's session stays usable).
    access_felix, resp_felix = login("student-felix")
    if access_felix is None or not isinstance(resp_felix, dict):
        check("auth: refresh + logout revocation", False, "student-felix login failed")
        return access
    status, resp = request("POST", "/auth/token/refresh", body={"refresh": resp_felix["tokens"]["refresh"]})
    # The refresh endpoint returns a flat token pair (TokenPairOut), not a "tokens" wrapper.
    refreshed = status == 200 and isinstance(resp, dict) and "access" in resp and "refresh" in resp
    status, _ = request("POST", "/auth/logout", token=access_felix)
    status_old, _ = request("GET", "/me", token=access_felix)
    check(
        "auth: refresh rotates, logout revokes old token",
        refreshed and status_old == 401,
        f"refreshed={refreshed} (status={status}) old_after_logout={status_old}",
    )
    return access


def verify_student(access: str) -> None:
    """3. The complete student flow on david's open instance (#2, anions)."""
    status, analyses = request("GET", "/analyses", token=access)
    if status != 200 or not isinstance(analyses, list):
        check("student: GET /analyses", False, f"status={status}")
        return
    by_number = {a["number"]: a for a in analyses}
    expected_status = {1: "open", 2: "open", 3: "too_early", 4: "too_late"}
    check(
        "student: 4 assigned analyses with expected window states",
        all(by_number.get(n, {}).get("window_status") == s for n, s in expected_status.items()),
        f"got={ {n: a.get('window_status') for n, a in by_number.items()} }",
    )
    inst2 = by_number.get(2, {})
    inst2_id = inst2.get("id")

    # Precondition: david has not submitted yet (run load_examples --reset first).
    check(
        "student: precondition - instance #2 has no submissions yet",
        inst2.get("submission_count") == 0,
        f"count={inst2.get('submission_count')} (run: uv run python manage.py load_examples --reset)",
    )

    status, detail = request("GET", f"/analyses/{inst2_id}", token=access)
    anion_symbols = [i["symbol"] for i in (detail or {}).get("anions", [])]
    expected_anions = {"Cl-", "SO4-2", "CO3-2", "NO3-", "Br-"}
    check(
        "student: detail shows possible ions (anions only for this type)",
        status == 200 and detail.get("cations") == [] and expected_anions == set(anion_symbols),
        f"cations={detail.get('cations')} anions={anion_symbols}",
    )
    check(
        "student: detail hides the correct set (no 'correct' field)",
        status == 200 and "correct_ions" not in (detail or {}),
    )

    status, subs = request("GET", f"/analyses/{inst2_id}/substances", token=access)
    check(
        "student: reference substances for the possible ions",
        status == 200 and isinstance(subs, list) and len(subs) > 0,
        f"count={len(subs) if isinstance(subs, list) else subs}",
    )

    cl = ion_id(detail.get("anions", []), "Cl-")
    so4 = ion_id(detail.get("anions", []), "SO4-2")
    co3 = ion_id(detail.get("anions", []), "CO3-2")
    _ions_status, ions = request("GET", "/ions", token=access)
    iod = ion_id(ions, "I-") if isinstance(ions, list) else None

    # 3.1 Correct first submission -> full score.
    k1 = uuid.uuid4().hex
    status, resp = request(
        "POST",
        f"/analyses/{inst2_id}/submissions",
        token=access,
        body={"ion_ids": [cl, so4], "confirmed": True, "idempotency_key": k1},
    )
    sub = (resp or {}).get("submission", {})
    check(
        "student: correct submission scores full (2/2 -> 20)",
        status == 200 and sub.get("score") == 20 and sub.get("correct_count") == 2 and sub.get("missing_count") == 0,
        f"status={status} resp={resp}",
    )
    first_id = sub.get("id")

    # 3.2 Idempotent replay -> same submission, no duplicate.
    status, resp = request(
        "POST",
        f"/analyses/{inst2_id}/submissions",
        token=access,
        body={"ion_ids": [cl, so4], "confirmed": True, "idempotency_key": k1},
    )
    check(
        "student: idempotency replay returns the same submission",
        status == 200 and (resp or {}).get("submission", {}).get("id") == first_id,
        f"status={status}",
    )

    # 3.3 Retry with one false positive -> penalty.
    k2 = uuid.uuid4().hex
    status, resp = request(
        "POST",
        f"/analyses/{inst2_id}/submissions",
        token=access,
        body={"ion_ids": [cl, so4, co3], "confirmed": True, "idempotency_key": k2},
    )
    sub = (resp or {}).get("submission", {})
    check(
        "student: retry with false positive -> 18 (20 - 2 penalty)",
        status == 200
        and sub.get("score") == 18
        and sub.get("wrong_count") == 1
        and sub.get("penalty") == 2
        and sub.get("submission_number") == 2,
        f"status={status} resp={resp}",
    )

    # 3.4 Ion outside the possible set is rejected.
    k3 = uuid.uuid4().hex
    status, resp = request(
        "POST",
        f"/analyses/{inst2_id}/submissions",
        token=access,
        body={"ion_ids": [iod], "confirmed": True, "idempotency_key": k3},
    )
    check("student: disallowed ion rejected (400)", status == 400, f"status={status} resp={resp}")

    # 3.5 Result endpoint reveals the answer key + best score.
    status, resp = request("GET", f"/analyses/{inst2_id}/result", token=access)
    check(
        "student: result shows answer key, 2 submissions, best total 20",
        status == 200
        and len((resp or {}).get("submissions", [])) == 2
        and resp.get("total_score") == 20
        and resp.get("ideal_score") == 20,
        f"status={status} resp={resp}",
    )

    # 3.6 Third submission -> penalty 4; fourth -> limit reached.
    k4 = uuid.uuid4().hex
    status, resp = request(
        "POST",
        f"/analyses/{inst2_id}/submissions",
        token=access,
        body={"ion_ids": [cl], "confirmed": True, "idempotency_key": k4},
    )
    sub = (resp or {}).get("submission", {})
    check(
        "student: 3rd submission -> 6 (10 - 4 penalty)",
        status == 200 and sub.get("score") == 6 and sub.get("penalty") == 4,
        f"status={status} resp={resp}",
    )
    k5 = uuid.uuid4().hex
    status, resp = request(
        "POST",
        f"/analyses/{inst2_id}/submissions",
        token=access,
        body={"ion_ids": [cl, so4], "confirmed": True, "idempotency_key": k5},
    )
    check("student: 4th submission rejected - limit reached (400)", status == 400, f"status={status} resp={resp}")

    # 3.7 Window enforcement: too_early and too_late instances reject submissions.
    inst3_id = by_number.get(3, {}).get("id")
    inst4_id = by_number.get(4, {}).get("id")
    status, _ = request(
        "POST",
        f"/analyses/{inst3_id}/submissions",
        token=access,
        body={"ion_ids": [], "confirmed": True, "idempotency_key": uuid.uuid4().hex},
    )
    check("student: too_early instance rejects submission (400)", status == 400, f"status={status}")
    status, _ = request(
        "POST",
        f"/analyses/{inst4_id}/submissions",
        token=access,
        body={"ion_ids": [], "confirmed": True, "idempotency_key": uuid.uuid4().hex},
    )
    check("student: too_late instance rejects submission (400)", status == 400, f"status={status}")

    # 3.8 Another student cannot see david's instance.
    access_emma, _ = login("student-emma")
    status, _ = request("GET", f"/analyses/{inst2_id}", token=access_emma or "")
    check("student: foreign instance not visible (404)", status == 404, f"status={status}")

    # 3.9 Summary aggregates scores.
    status, resp = request("GET", "/me/summary", token=access)
    check(
        "student: summary -> total 20 / ideal 90",
        status == 200 and (resp or {}).get("total_score") == 20 and resp.get("ideal_score") == 90,
        f"status={status} resp={resp}",
    )


def verify_seeded() -> None:
    """4. The pre-seeded submissions are graded as documented."""
    _, resp = login("student-anna")
    if not isinstance(resp, dict):
        check("seeded: anna login", False)
        return
    a1 = next((a for a in resp["analyses"] if a["number"] == 1), {})
    check(
        "seeded: anna's instance #1 is submitted with score 20",
        a1.get("window_status") == "submitted" and a1.get("score") == 20,
        f"got={a1}",
    )

    _, resp = login("student-ben")
    if not isinstance(resp, dict):
        check("seeded: ben login", False)
        return
    a1 = next((a for a in resp["analyses"] if a["number"] == 1), {})
    check(
        "seeded: ben's instance #1 has 2 submissions, best score 18",
        a1.get("submission_count") == 2 and a1.get("score") == 18,
        f"got={a1}",
    )


def verify_assistant() -> None:
    """5. Assistant views: roster, stats, per-student detail, CSV export."""
    access, resp = login("assistant.bio")
    if access is None:
        check("assistant: login", False, f"resp={resp}")
        return
    check("assistant: login role is assistant", isinstance(resp, dict) and resp["user"]["role"] == "assistant")

    status, courses = request("GET", "/assistant/courses", token=access)
    if status != 200 or not isinstance(courses, list):
        check("assistant: GET /assistant/courses", False, f"status={status}")
        return
    check(
        "assistant: sees exactly the assigned biology course",
        len(courses) == 1 and "Biology" in courses[0]["name"],
        f"got={[c['name'] for c in courses]}",
    )
    bio = courses[0]
    stats = bio.get("stats", {})
    usernames = {s["username"] for s in bio.get("students", [])}
    check(
        "assistant: roster lists all 6 biology students with barcodes",
        len(usernames) == 6 and all(s.get("barcode") for s in bio.get("students", [])),
        f"students={sorted(usernames)}",
    )
    check(
        "assistant: stats reflect 24 assignments, 3 submitted (anna, ben, david)",
        stats.get("total_assignments") == 24 and stats.get("submitted") == 3 and stats.get("pending") == 21,
        f"stats={stats}",
    )
    check("assistant: average score computed", (stats.get("average_score") or 0) > 0, f"stats={stats}")

    david_entry = next((s for s in bio["students"] if s["username"] == "student-david"), {})
    check("assistant: david's roster entry has 4 analyses", len(david_entry.get("analyses", [])) == 4)

    status, csv_text = request("GET", f"/assistant/courses/{bio['id']}/export/csv", token=access, raw=True)
    check(
        "assistant: CSV export with submissions",
        status == 200
        and isinstance(csv_text, str)
        and csv_text.startswith("student_username,")
        and "student-david" in csv_text
        and "student-anna" in csv_text,
        f"status={status} head={str(csv_text)[:80]!r}",
    )

    status, ov = request("GET", f"/assistant/courses/{bio['id']}/substance-overview", token=access)
    analyses_ov = (ov or {}).get("analyses", [])
    expected_units = sum(a["sample_count"] * len(a["substances"]) for a in analyses_ov)
    totals_consistent = (
        isinstance(ov, dict)
        and len(analyses_ov) == 4
        and all(len(a["substances"]) > 0 for a in analyses_ov)
        and ov.get("total_units") == expected_units
        and ov.get("distinct_substances") == len(ov.get("totals", []))
        and all(t["count"] > 0 and t["used_in_analyses"] > 0 for t in ov.get("totals", []))
    )
    check(
        "assistant: substance overview lists all 4 analyses with their substances",
        totals_consistent,
        f"status={status} analyses={len(analyses_ov)} "
        f"total_units={ov.get('total_units') if isinstance(ov, dict) else '-'} expected={expected_units}",
    )
    status2, ov2 = request(
        "GET", f"/assistant/courses/{bio['id']}/substance-overview?samples_per_analysis=1", token=access
    )
    analyses_ov2 = (ov2 or {}).get("analyses", [])
    expected_units_1 = sum(len(a["substances"]) for a in analyses_ov2)
    check(
        "assistant: substance overview honours samples_per_analysis=1",
        status2 == 200
        and isinstance(ov2, dict)
        and ov2.get("samples_per_analysis") == 1
        and all(a["sample_count"] == 1 for a in analyses_ov2)
        and ov2.get("total_units") == expected_units_1,
        f"status={status2} total_units={ov2.get('total_units') if isinstance(ov2, dict) else '-'}",
    )
    access_student, _ = login("student-anna")
    status3, _ = request("GET", f"/assistant/courses/{bio['id']}/substance-overview", token=access_student or "")
    check("assistant: student cannot open the substance overview (403)", status3 == 403, f"status={status3}")

    david_id = david_entry.get("id")
    status, detail = request("GET", f"/assistant/students/{david_id}/submissions", token=access)
    entries = detail if isinstance(detail, list) else []
    david_s1 = next((e for e in entries if e.get("analysis", "").startswith("Analysis 1")), None)
    correct_symbols = {i["symbol"] for i in (david_s1 or {}).get("correct_ions", [])}
    check(
        "assistant: per-student submissions include answer key",
        status == 200
        and david_s1 is not None
        and correct_symbols == {"Na+", "K+"}
        and len((david_s1 or {}).get("submissions", [])) == 0,
        f"status={status} correct={correct_symbols}",
    )

    # The pharmacy assistant sees only the pharmacy course.
    access_p, _ = login("assistant.pharma")
    status, courses_p = request("GET", "/assistant/courses", token=access_p or "")
    check(
        "assistant: pharma assistant sees only pharmacy course (2 students, 4 assignments)",
        status == 200
        and isinstance(courses_p, list)
        and len(courses_p) == 1
        and "Pharmacy" in courses_p[0]["name"]
        and len(courses_p[0]["students"]) == 2
        and courses_p[0]["stats"]["total_assignments"] == 4,
        f"status={status}",
    )


def verify_admin() -> None:
    """6. Admin API: courses, types, instances, assignments, settings."""
    access, resp = login("admin")
    if access is None:
        check("admin: login", False, f"resp={resp}")
        return
    check("admin: login role is admin", isinstance(resp, dict) and resp["user"]["role"] == "admin")

    status, courses = request("GET", "/admin/courses", token=access)
    course_names = {c.get("name") for c in courses} if isinstance(courses, list) else set()
    check(
        "admin: lists the 3 dataset courses",
        status == 200
        and isinstance(courses, list)
        and {
            "Inorganic Chemistry WS 2026 - Biology",
            "Inorganic Chemistry WS 2026 - Pharmacy",
            "Inorganic Chemistry SS 2026 - Materials",
        }
        <= course_names,
        f"status={status} courses={sorted(course_names)}",
    )
    bio_id = next((c["id"] for c in courses if "Biology" in c.get("name", "")), None)

    temp_name = f"E2E Temp Course {uuid.uuid4().hex[:6]}"
    status, created = request(
        "POST",
        "/admin/courses",
        token=access,
        body={"name": temp_name, "semester": "E2E", "track": "e2e", "is_active": False},
    )
    check(
        "admin: create course",
        status in (200, 201) and isinstance(created, dict) and "id" in created,
        f"status={status} resp={created}",
    )

    status, types = request("GET", "/admin/analysis-types", token=access)
    check(
        "admin: lists 4 analysis types",
        status == 200 and isinstance(types, list) and len(types) == 4,
        f"status={status} n={len(types) if isinstance(types, list) else '-'}",
    )

    status, instances = request("GET", f"/admin/analysis-instances?course_id={bio_id}", token=access)
    check(
        "admin: lists 24 biology instances (6 students x 4)",
        status == 200 and isinstance(instances, list) and len(instances) == 24,
        f"status={status} n={len(instances) if isinstance(instances, list) else '-'}",
    )

    status, assignments = request("GET", f"/admin/assignments?course_id={bio_id}", token=access)
    check(
        "admin: lists 24 biology assignments",
        status == 200 and isinstance(assignments, list) and len(assignments) == 24,
        f"status={status} n={len(assignments) if isinstance(assignments, list) else '-'}",
    )

    status, gc = request("GET", "/admin/grading-config", token=access)
    check(
        "admin: grading config loaded (per_ion, max 3)",
        status == 200 and gc.get("grading_mode") == "per_ion" and gc.get("max_submissions_per_analysis") == 3,
        f"resp={gc}",
    )
    payload = dict(gc)
    payload["false_positive_deduction"] = 1
    status, gc2 = request("PUT", "/admin/grading-config", token=access, body=payload)
    payload["false_positive_deduction"] = 0
    status2, gc3 = request("PUT", "/admin/grading-config", token=access, body=payload)
    check(
        "admin: grading config round-trip update",
        status == 200
        and gc2.get("false_positive_deduction") == 1
        and status2 == 200
        and gc3.get("false_positive_deduction") == 0,
        f"after={gc2} restored={gc3}",
    )

    status, settings = request("GET", "/admin/app-settings", token=access)
    check(
        "admin: app settings point at the active biology course",
        status == 200 and settings.get("active_course_id") == bio_id and settings.get("analyses_per_course") == 4,
        f"resp={settings} bio_id={bio_id}",
    )
    settings_payload = dict(settings)
    settings_payload["analyses_per_course"] = 5
    status, s2 = request("PUT", "/admin/app-settings", token=access, body=settings_payload)
    settings_payload["analyses_per_course"] = 4
    status2, s3 = request("PUT", "/admin/app-settings", token=access, body=settings_payload)
    check(
        "admin: app settings round-trip update",
        status == 200
        and s2.get("analyses_per_course") == 5
        and status2 == 200
        and s3.get("analyses_per_course") == 4
        and s3.get("active_course_id") == bio_id,
        f"after={s2} restored={s3}",
    )


def verify_substances_and_rbac(david_access: str) -> None:
    """7. Substance catalog + role-based access control."""
    status, ions = request("GET", "/ions", token=david_access)
    n_cation = len([i for i in ions if i.get("kind") == "cation"]) if isinstance(ions, list) else -1
    check(
        "substances: 22 ions (12 cations)",
        status == 200 and isinstance(ions, list) and len(ions) == 22 and n_cation == 12,
        f"status={status} n={len(ions) if isinstance(ions, list) else '-'}",
    )
    status, cations = request("GET", "/ions?kind=cation", token=david_access)
    check(
        "substances: filter by kind works",
        status == 200 and isinstance(cations, list) and len(cations) == 12,
        f"n={len(cations) if isinstance(cations, list) else '-'}",
    )

    status, substances = request("GET", "/substances", token=david_access)
    check(
        "substances: 35 substances in catalog",
        status == 200 and isinstance(substances, list) and len(substances) == 35,
        f"n={len(substances) if isinstance(substances, list) else '-'}",
    )
    na = next((i for i in (ions or []) if i.get("symbol") == "Na+"), None)
    status, with_na = request("GET", f"/substances?ion_id={na['id']}", token=david_access) if na else (0, None)
    check(
        "substances: filter by ion (Na+ salts)",
        status == 200 and isinstance(with_na, list) and len(with_na) >= 5,
        f"n={len(with_na) if isinstance(with_na, list) else '-'}",
    )

    # RBAC: students cannot use the admin-only ion CRUD.
    status, _ = request(
        "POST", "/ions", token=david_access, body={"symbol": "E2E2+", "name": "E2E Ion", "kind": "cation"}
    )
    check("rbac: student cannot create ions (403)", status == 403, f"status={status}")
    access_admin, _ = login("admin")
    status, created = request(
        "POST", "/ions", token=access_admin or "", body={"symbol": "E2E2+", "name": "E2E Ion", "kind": "cation"}
    )
    ion_id_created = created.get("id") if isinstance(created, dict) else None
    check(
        "rbac: admin can create ions",
        status in (200, 201) and ion_id_created is not None,
        f"status={status} resp={created}",
    )
    if ion_id_created:
        status, _ = request("DELETE", f"/ions/{ion_id_created}", token=access_admin or "")
        check("rbac: admin can delete ions again", status in (200, 204), f"status={status}")


def main() -> int:
    """Run every verification section; return 0 only if all checks pass."""
    print(f"FlameCheck E2E verification against {API}\n")
    verify_frontend()
    print()
    david_access = verify_auth()
    print()
    if david_access is None:
        print("Aborting: student-david login failed - cannot continue.")
        return 1
    verify_student(david_access)
    print()
    verify_seeded()
    print()
    verify_assistant()
    print()
    verify_admin()
    print()
    verify_substances_and_rbac(david_access)

    total = len(_results)
    failed = [r for r in _results if not r[0]]
    print()
    print(f"{'=' * 64}")
    print(f"Result: {total - len(failed)}/{total} checks passed")
    if failed:
        print("Failed checks:")
        for _, name, detail in failed:
            print(f"  - {name}" + (f"  ({detail})" if detail else ""))
        return 1
    print("All checks passed - the full app works with the example dataset.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
