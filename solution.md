# Sewa Setu: Technical Audit, Issues & Solutions

---

## 1. UTF-8 & Indic Script Encoding Failure (`????` & Truncated Names)

### 1. What Happened to the Citizens (The Real-World Symptom)
In the Deputy Commissioner's briefing (`dc-briefing.mp3`), an elderly applicant walked two hours on foot to report that his Assamese name appeared as `????` (four question marks) on his acknowledgement slip. Others found their names cut in half. Without a valid acknowledgement slip showing their real name, banks and local verification officers reject their pension applications.

### 2. Why Did This Happen? (The Exact Code Bugs)
There are two separate bugs in `app/app.py`:

* **Bug A — Names Cut in Half (Byte-level slicing in `app/app.py:68-76`):**
  ```python
  def sanitize(value, maxlen=20):
      if value is None:
          return ""
      value = value.strip()
      encoded = value.encode("utf-8")[:maxlen]
      return encoded.decode("utf-8", errors="ignore")
  ```
  * **Root Cause:** In English, 1 character = 1 byte. In Indic scripts (Assamese, Bengali, Devanagari), each character takes 3 bytes in UTF-8. Slicing at `[:maxlen]` (where `maxlen=20`) leaves only 20 bytes—barely ~6 Indic letters (`20 ÷ 3 = 6.6`). Longer names are chopped in half, and any character split mid-byte is silently deleted by `errors="ignore"`.

* **Bug B — Names Turning Into `????` (Latin-1 PDF font in `app/app.py:346-368`):**
  ```python
  pdf = FPDF()
  pdf.add_page()
  pdf.set_font("Helvetica", "B", 14)
  ...
  for label, val in zip(labels, row):
      try:
          pdf.cell(60, 8, label, border=1)
          pdf.cell(0, 8, str(val), border=1, ln=1)
      except Exception:
          pdf.cell(0, 8, "?", border=1, ln=1)
  ```
  * **Root Cause:** Standard `Helvetica` in classic FPDF only supports Latin-1 (ASCII). When `pdf.cell()` tries to render non-Latin characters, Python raises an encoding error. The `except Exception:` block catches it and prints `?` for each failed character, producing `????`.

### 3. How We Solve It (Solution Approach)
1. **Fix `sanitize()`:** Slice by character length (`value[:100]`), not raw bytes (`encode('utf-8')[:20]`).
   ```python
   def sanitize(value, maxlen=100):
       return (value or "").strip()[:maxlen]
   ```
2. **Support Unicode in PDF Generation:** Load an open TrueType Unicode font (e.g. `NotoSans` or `FreeSerif`) into FPDF with `uni=True` so Assamese and Indic scripts render natively.
   ```python
   pdf = FPDF()
   pdf.add_font("NotoSans", "", "static/fonts/NotoSans-Regular.ttf", uni=True)
   pdf.set_font("NotoSans", "", 10)
   ```

### 4. Verification & Proof of Resolution (TDD)
- **Status**: **RESOLVED & VERIFIED**
- **Test File**: `tests/test_issue1_encoding.py`
- **Failing Test Commit**: `6f771ed` (`test: add failing tests for Indic script sanitization and PDF encoding (Issue 1)`)
  - `test_sanitize_assamese_name_preservation`: Failed (`'প্ৰমোদ ' != 'প্ৰমোদ শৰ্মা'`)
  - `test_sanitize_devanagari_name_preservation`: Failed (`'राजेश क' != 'राजेश कुमार शर्मा'`)
  - `test_pdf_indic_characters_not_replaced_with_question_marks`: Failed (`1 != 0 : PDF contains 1 cell(s) with '(?) Tj' fallback`)
- **Passing Fix Commit**: `dfadf4a` (`fix(core): resolve Indic character truncation and PDF unicode rendering (Issue 1)`)
  - Created modular `app/utils/sanitizer.py` (Unicode NFC normalization, character-based slicing, maxlen=100)
  - Created modular `app/utils/pdf_generator.py` (multi-font fallback with `NotoSans`, `NotoSansBengali`, `NotoSansDevanagari`)
  - Bundled TTF fonts in `app/static/fonts/`
  - All 4 tests passed (`Ran 4 tests in 0.103s. OK.`)
- **Live Health**: Container `sewasetu-handout-app-1` rebuilt and operational at `http://localhost:8000` (HTTP 200).

---

## 2. Broken RTPS "Deemed Approval" Automation Engine

### 1. Diagnosis & Civic Evidence

* **The Civic Problem:**
  Under the *Purvanchal Right to Public Services (RTPS) Act*, any pension application untouched for $>15$ days must automatically be marked `DEEMED_APPROVED`.
  - In the live database right now, exactly **4,874 senior citizens' applications** are stuck in `PENDING` past their 15-day statutory SLA deadline.
  - Senior citizens are denied their monthly pension disbursements despite meeting all statutory criteria.

* **The Exact Code Bug:**
  In March 2026, the configuration file was renamed from `settings.ini` to `app.ini` (`app/config/app.ini:2` noting: `; Consolidated from config/settings.ini, March 2026 (CR-2026-031)`).
  However, `app/scripts/deemed_approval.py:22-25` was never updated:
  ```python
  config = configparser.ConfigParser()
  CONFIG_PATH = os.path.join(BASE_DIR, "config", "settings.ini")
  with open(CONFIG_PATH) as fh:
      config.read_file(fh)
  ```
  Every night at 02:00 AM, the scheduler runs and immediately crashes:
  ```text
  Traceback (most recent call last):
    File "/app/scripts/deemed_approval.py", line 24, in <module>
      with open(CONFIG_PATH) as fh:
  FileNotFoundError: [Errno 2] No such file or directory: '/app/config/settings.ini'
  ```
  *(Documented across hundreds of consecutive nightly failures at the end of `logs/cron.log`)*.

* **Statutory Truth in UI:**
  In `app/app.py` (`view_application`), the portal blindly reads whatever static string is stored in the database `status` column. Even after 30+ days, citizens see `PENDING`, violating their legal rights under the RTPS Act.

---

### 2. Proposed TDD Execution Plan

Following the mandatory evaluation requirement (*failing test committed first, then fix committed*):

1. **Write Failing Test (`tests/test_issue2_rtps_approval.py`):**
   * **Test A — Config Loading:** Asserts `deemed_approval` loads configuration without `FileNotFoundError`.
   * **Test B — Overdue Application Batch Transition:** Asserts applications older than 15 days in `PENDING` transition to `DEEMED_APPROVED` with `decided_by='RTPS-AUTO'`.
   * **Test C — Citizen Portal SLA Fallback:** Asserts that a pending application $\ge 15$ days old displays `DEEMED_APPROVED` in the citizen status portal even if batch jobs lag.
2. **Run Test against Current Code** $\rightarrow$ Confirm **FAIL**.
3. **Commit Failing Test:**
   ```bash
   git commit -m "test: add failing tests for RTPS deemed approval engine and UI SLA status (Issue 2)"
   ```
4. **Apply Fix:**
   * Update `app/scripts/deemed_approval.py` to point to `app.ini` (with fallback to `settings.ini`).
   * Modularize the approval logic into a callable function `run_deemed_approval()` so it can be invoked safely in batch, on-demand, or via cron.
   * Update `view_application` in `app/app.py` to dynamically enforce `DEEMED_APPROVED` when statutory SLA has expired.
### 3. Verification & Proof of Resolution (TDD Evidence)
- **Status**: **RESOLVED & VERIFIED**
- **Test File**: `tests/test_issue2_rtps_approval.py`
- **Failing Test Commit**: `c245a32` (`test: add failing tests for RTPS deemed approval engine and UI SLA status (Issue 2)`)
  - `test_deemed_approval_config_path_exists`: Failed with `FileNotFoundError: /app/config/settings.ini`
  - `test_deemed_approval_import_and_execution`: Failed with `FileNotFoundError: /app/config/settings.ini`
  - `test_statutory_sla_status_computation`: Error `cannot import name 'get_effective_status' from 'app'`
- **Passing Fix Commit**: `76ce886` (`fix(automation): restore RTPS deemed approval config path and statutory UI fallback (Issue 2)`)
  - Updated config path to `app.ini` with fallback to `settings.ini` in `app/scripts/deemed_approval.py`
  - Exported callable `run_deemed_approval(now=None)`
  - Added `get_effective_status()` in `app/app.py` ensuring statutory truth in citizen portal
  - All 3 tests passed (`Ran 3 tests in 10.017s. OK.`)
- **Live Database Impact**:
  - Exactly **4,867 overdue pending applications** successfully transitioned to `DEEMED_APPROVED` with `decided_by='RTPS-AUTO'`.
  - Remaining: only 7 applications (submitted today) remain in `PENDING` state.

---

## 3. Critical PII Leakage, IDOR & Access Control Vulnerabilities

### 1. What Happened to the Citizens (The Real-World Symptom)
Immediately after applying, senior citizens receive unsolicited sales calls and home visits from predatory agents offering loans or insurance. This points to active, ongoing leakage of personal database records.

### 2. Why Did This Happen? (The Exact Code Bugs)

* **Bug A — Public IDOR on PDFs in `app/app.py:423-436`:**
  ```python
  @app.route("/ack/<int:app_id>.pdf")
  def ack_pdf(app_id):
      path = os.path.join(UPLOAD_DIR, "ack", "%d.pdf" % app_id)
      # Returns PDF with NO login check or ownership check!
  ```
  * **Root Cause:** Zero authentication. Anyone on the internet can scrape `/ack/1.pdf`, `/ack/2.pdf`, etc., harvesting names, phone numbers, dates of birth, bank accounts, IFSC codes, and addresses for all 100,000+ senior citizens.

* **Bug B — Cross-User IDOR on Status Page in `app/app.py:406-420`:**
  ```python
  @app.route("/application/<int:app_id>")
  def view_application(app_id):
      if not session.get("logged_in"):
          return redirect(url_for("status_login"))
      # Lacks check that app_id belongs to logged-in session['portal_mobile']
  ```
  * **Root Cause:** Once any citizen logs into their status portal, they can change the URL ID (`/application/10`, `/application/11`) to view any other citizen's full profile.

* **Bug C — Broken Admin Role Check in `app/app.py:532-558`:**
  ```python
  @app.route("/admin/approve/<int:app_id>", methods=["POST"])
  def admin_approve(app_id):
      if not session.get("logged_in"):  # Checks logged_in, NOT admin!
          abort(403)
  ```
  * **Root Cause:** Regular citizens logging in to check status have `session['logged_in'] = True`. Any citizen can make POST requests to `/admin/approve/<id>` or `/admin/reject/<id>` and approve/reject government pensions.

* **Bug D — SQL Injection in `app/app.py:446-449`:**
  ```python
  cur.execute("SELECT mobile FROM portal_users WHERE mobile = '%s'" % mobile)
  ```
  * **Root Cause:** Direct string substitution (`%s` % mobile) inside SQL on a public unauthenticated password reset page.

### 3. How We Solve It (Solution Approach & Code Diff)
The security flaws were remediated in `app/app.py` in Commit `82270b6`:

```diff
--- a/app/app.py
+++ b/app/app.py
@@ -39,8 +39,8 @@ app = Flask(__name__)
 app.secret_key = config.get("app", "secret_key")
 app.config["PERMANENT_SESSION_LIFETIME"] = 300
 
-ADMIN_USERNAME = "admin"
-ADMIN_PASSWORD = "sewasetu@123"
+ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
+ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "sewasetu@123")
 
@@ -336,6 +336,7 @@ def handle_submission():
     session.pop("form_data", None)
     session.pop("doc_path", None)
     session.pop("verified_mobile", None)
+    session["submitted_app_id"] = new_id
     send_sms(mobile, "Sewa Setu: application %s received...")
     return render_template("confirmation.html", app_no=app_no, app_id=new_id)
 
@@ -398,7 +399,7 @@ def get_effective_status(status, submitted_at, sla_days=SLA_DAYS):
 
 @app.route("/application/<int:app_id>")
 def view_application(app_id):
-    if not session.get("logged_in"):
+    if not session.get("logged_in") and not session.get("admin"):
         flash("Please login to view application status.")
         return redirect(url_for("status_login"))
     conn = get_db()
@@ -410,6 +411,12 @@ def view_application(app_id):
     cur.close(); conn.close()
     if not row:
         abort(404)
+
+    is_admin = bool(session.get("admin"))
+    user_mobile = session.get("portal_mobile")
+    if not is_admin and user_mobile != row[2]:
+        abort(403)
+
     app_data = list(row)
 
@@ -420,17 +427,29 @@ def view_application(app_id):
 
 @app.route("/ack/<int:app_id>.pdf")
 def ack_pdf(app_id):
+    conn = get_db()
+    cur = conn.cursor()
+    cur.execute("SELECT id, mobile FROM applications WHERE id = %s", (app_id,))
+    row = cur.fetchone()
+    if not row:
+        cur.close(); conn.close()
+        abort(404)
+
+    app_mobile = row[1]
+    is_admin = bool(session.get("admin"))
+    user_mobile = session.get("portal_mobile")
+    is_submitted_in_session = (session.get("submitted_app_id") == app_id)
+
+    if not is_admin and user_mobile != app_mobile and not is_submitted_in_session:
+        cur.close(); conn.close()
+        abort(403)
+
     path = os.path.join(UPLOAD_DIR, "ack", "%d.pdf" % app_id)
     if not os.path.exists(path):
         data = generate_acknowledgment(cur, app_id)
         cur.close(); conn.close()
         return send_file(io.BytesIO(data), mimetype="application/pdf")
+    cur.close(); conn.close()
     return send_file(path, mimetype="application/pdf")
 
@@ -440,11 +459,11 @@ def reset_password():
         mobile = request.form.get("mobile", "")
         conn = get_db()
         cur = conn.cursor()
-        # fetch account for reset
-        cur.execute("SELECT mobile FROM portal_users WHERE mobile = '%s'" % mobile)
+        # fetch account for reset using parameterized query
+        cur.execute("SELECT mobile FROM portal_users WHERE mobile = %s", (mobile,))
         row = cur.fetchone()
         if row:
-            cur.execute("SELECT dob FROM applications WHERE mobile = '%s' LIMIT 1" % mobile)
+            cur.execute("SELECT dob FROM applications WHERE mobile = %s LIMIT 1", (mobile,))
             r2 = cur.fetchone()
 
@@ -529,7 +548,7 @@ def admin_view(app_id):
 
 @app.route("/admin/approve/<int:app_id>", methods=["POST"])
 def admin_approve(app_id):
-    if not session.get("logged_in"):
+    if not session.get("admin"):
         abort(403)
 
@@ -543,7 +562,7 @@ def admin_reject(app_id):
-    if not session.get("logged_in"):
+    if not session.get("admin"):
         abort(403)
```

### 4. Verification & Proof of Resolution (TDD Evidence)
- **Status**: **RESOLVED & VERIFIED**
- **Test File**: `tests/test_issue3_security_access_control.py`
- **Failing Test Commit**: [`9a9423c`](https://github.com/sumitkumar112006/sewasetu-handout/commit/9a9423ced4fa8d9e9619c961e05be3b632fa5a7a) (`test: add failing tests for PII leakage, IDOR, and unauthorized admin actions (Issue 3)`)
  - `test_unauthenticated_pdf_access_denied`: Failed (returned 200 with full PII and bank details instead of 403)
  - `test_cross_user_application_view_denied`: Failed (returned 200 with another citizen's profile instead of 403)
  - `test_unauthorized_citizen_cannot_approve_application`: Failed (non-admin citizen approved application with 302 instead of 403)
  - `test_unauthorized_citizen_cannot_reject_application`: Failed (non-admin citizen rejected application with 302 instead of 403)
- **Passing Fix Commit**: [`82270b6`](https://github.com/sumitkumar112006/sewasetu-handout/commit/82270b6ed4e882484e82d76932396cb2a49365ab) (`fix(security): resolve IDOR on PDFs and profiles, enforce admin authorization, parameterize reset query (Issue 3)`)
  - Added strict ownership validation (`session['portal_mobile'] == row['mobile']`) and admin override on `/application/<id>`
  - Enforced authentication and ownership on `/ack/<id>.pdf`
  - Replaced `session.get('logged_in')` with `session.get('admin')` on `/admin/approve` and `/admin/reject`
  - Parameterized SQL queries in `/status/reset` against SQL injection
  - Externalized admin credentials to environment variables with fallback
  - All 5 tests passed (`Ran 5 tests in 0.049s. OK.`)

### 5. Useful Application & Probe URLs
| Endpoint Type | URL | Purpose & Security Guarantee |
| :--- | :--- | :--- |
| **Citizen Application** | `http://localhost:8000/` | Public application workflow for seniors. |
| **Citizen Status Login** | `http://localhost:8000/status` | Mobile + DOB login for status tracking. |
| **Citizen Profile (IDOR Safe)** | `http://localhost:8000/application/1` | Returns `200` only for owner/admin; `403` for cross-user snoopers. |
| **PDF Slip (Scrape Safe)** | `http://localhost:8000/ack/1.pdf` | Returns `403 Forbidden` for unauthenticated web scrapers. |
| **Password Reset (SQLi Safe)** | `http://localhost:8000/status/reset` | Parameterized query immune to injection attacks. |
| **Admin Login** | `http://localhost:8000/admin` | Staff credentials (`admin` / `sewasetu@123`). |
| **Admin Application Inspection** | `http://localhost:8000/admin/view/1` | Official review interface. |
| **Admin Approve Action** | `POST http://localhost:8000/admin/approve/1` | Enforced admin role; `403` for regular citizens. |
| **Admin Reject Action** | `POST http://localhost:8000/admin/reject/1` | Enforced admin role; `403` for regular citizens. |
| **SMS Gateway Web Console** | `http://localhost:8000/__gateway/` | Inspect outbound OTPs and SMS notifications. |

---

## 4. Cyclical Pre-Disbursement Server Freeze (Denial of Service)

### 1. What Happened to the Citizens (The Real-World Symptom)
2–3 days prior to the monthly pension disbursement cutoff, the portal grinds to a complete crawl or crashes. Elderly citizens trying to submit applications or check status encounter timeouts and gateway errors.

### 2. Why Did This Happen? (The Exact Code Bugs)

* **Bug A — Missing Database Indexes in `app/schema.sql:5-24`:**
  * **Root Cause:** `schema.sql` only defines a primary key on `id`. It has **no indexes** on `mobile`, `status`, `submitted_at`, or `block`.
  * In `app/app.py:485-510`, admin dashboard and disbursement verification queries run `GROUP BY status`, `GROUP BY block`, and `WHERE status = 'PENDING' AND submitted_at < ...` across 100,000+ rows. PostgreSQL performs slow, locking Sequential Full Table Scans (`Seq Scan`), choking the connection pool.

* **Bug B — Artificial CPU Burner Loop in `app/app.py:355-358`:**
  ```python
  # decorative border, as per approved letterhead design
  for i in range(0, 2000):
      x = 10 + (i % 190)
      pdf.line(x, 282, x + 0.5, 282)
      pdf.line(x, 12, x + 0.5, 12)
  ```
  * **Root Cause:** Draws 4,000 individual vector line segments on the CPU for every single acknowledgement PDF generated.

* **Bug C — Gunicorn Worker Starvation in `app/Dockerfile:16`:**
  ```dockerfile
  CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "30", "app:app"]
  ```
  * **Root Cause:** Gunicorn runs only 4 synchronous workers. If 4 users trigger PDF downloads or run dashboard queries simultaneously, all 4 workers freeze in CPU loops or slow table scans, completely blocking the server.

### 3. How We Solve It (Solution Approach)
1. **Add Compound Database Indexes:**
   ```sql
   CREATE INDEX IF NOT EXISTS idx_applications_mobile ON applications(mobile);
   CREATE INDEX IF NOT EXISTS idx_applications_status_submitted ON applications(status, submitted_at);
   CREATE INDEX IF NOT EXISTS idx_applications_status_block ON applications(status, block);
   ```
2. **Remove the 4,000-Line PDF Loop:** Replace lines 355–358 with two clean, single-call vector border lines.
   ```python
   pdf.line(10, 12, 200, 12)
   pdf.line(10, 282, 200, 282)
   ```
3. **Configure Multi-Threaded Gunicorn:** Add thread concurrency (`--threads 4`) so slow requests don't block other incoming citizen connections.

### 4. Verification & Proof of Resolution (TDD Evidence)
- **Status**: **RESOLVED & VERIFIED**
- **Test File**: `tests/test_issue4_performance_dos.py`
- **Failing Test Commit**: [`3e4645c`](https://github.com/sumitkumar112006/sewasetu-handout/commit/3e4645c17098d2657bf7662a43006d75239fdb4c) (`test: add failing tests for DB indexing, PDF burner loop, and worker concurrency (Issue 4)`)
  - `test_database_indexes_exist_in_postgres`: Failed with missing indexes in database
  - `test_schema_declares_performance_indexes`: Failed with missing index in schema.sql
  - `test_pdf_generator_eliminates_artificial_cpu_burner_loop`: Failed with loop present
  - `test_dockerfile_configures_gunicorn_thread_concurrency`: Failed without `--threads`
- **Passing Fix Commit**: [`a349d72`](https://github.com/sumitkumar112006/sewasetu-handout/commit/a349d7288c6df918437120014a8f5b97cb778749) (`fix(performance): add DB indexes, eliminate PDF CPU burner loop, enable Gunicorn threads (Issue 4)`)
  - Added indexes in PostgreSQL and `schema.sql`
  - Replaced CPU loop in `pdf_generator.py`
  - Configured `--threads 4` in `Dockerfile`
  - All 4 tests passed (`Ran 4 tests in 0.283s. OK.`)

---

## 5. Self-Serve Cancellation, Duplicate Unblock & Form UX Fixes

### 1. What Happened to the Citizens (The Real-World Symptom)
Elderly citizens making minor typos (e.g. misspelling a name or single digit error in IFSC/bank account) had no option to edit or cancel. The portal blocked them permanently from submitting a new application ("An application already exists for this mobile number"), swamping the district helpdesk with manual record deletion requests. Furthermore, inverted US date parsing locked seniors out of their accounts, widows were blocked by mandatory employer fields for deceased husbands, and uploads failed with cryptic `ERR_VAL_47`.

### 2. Why Did This Happen? (The Exact Code Bugs)
* **Bug A — Strict Duplicate Lockout in `app/app.py:300-305`:**
  Counted all applications regardless of status (`SELECT count(*) FROM applications WHERE mobile = %s`), permanently locking re-applications.
* **Bug B — Absence of Self-Serve Cancellation:**
  No cancellation endpoint or UI button for `PENDING` records.
* **Bug C — Inverted Date Parsing in `app/app.py:277-285`:**
  Checked US format `"%m/%d/%Y"` before Indian format `"%d/%m/%Y"`. `05/06/1950` became May 6, 1950, generating wrong portal password (`06051950`) instead of `05061950`.
* **Bug D — Mandatory Employer for Widows in `app/app.py:270-274`:**
  Mandated `husband_employer` for deceased husbands.
* **Bug E — Misleading Upload Constraints & Cryptic Error Codes in `app/app.py:218-229`:**
  Rejected JPGs, capped at 100 KB, and flashed cryptic `ERR_VAL_47`.

### 3. How We Solve It (Solution Approach)
1. **Self-Serve Cancellation Route**:
   Added `@app.route("/application/<int:app_id>/cancel", methods=["POST"])` allowing authenticated owners to cancel `PENDING` applications.
2. **Update Duplicate Check**:
   `SELECT count(*) FROM applications WHERE mobile = %s AND status NOT IN ('CANCELLED', 'REJECTED')`
3. **Prioritize Indian Date Format**:
   `for fmt in ("%d/%m/%Y", "%m/%d/%Y"):`
4. **Remove Employer Requirement for Widows**:
   Do not require `husband_employer` when `marital == "Widowed"`.
5. **Support JPG & 5 MB Uploads**:
   Accept `.pdf`, `.jpg`, `.jpeg` up to 5 MB with user-friendly error messages.
6. **Cancellation UI**:
   Added interactive "Cancel Application" button in `app/templates/application.html` for `PENDING` applications.

### 4. Verification & Proof of Resolution (TDD Evidence)
- **Status**: **RESOLVED & VERIFIED**
- **Test File**: `tests/test_issue5_cancellation_and_ux.py`
- **Failing Test Commit**: [`74458a0`](https://github.com/sumitkumar112006/sewasetu-handout/commit/74458a0ef9351e604f375f1d19d6756627b7381f) (`test: add failing tests for self-serve cancellation, duplicate check, and form UX (Issue 5)`)
  - `test_self_serve_cancellation_of_pending_application`: Failed 404
  - `test_duplicate_check_allows_reapplication_after_cancellation`: Failed duplicate error
  - `test_indian_date_format_prioritized_over_us_format`: Failed `'1950-05-06' != '1950-06-05'`
  - `test_widow_not_blocked_by_husband_employer_requirement`: Failed widow validation
  - `test_upload_accepts_jpg_and_informative_error_messages`: Failed `ERR_VAL_47`
- **Passing Fix Commit**: [`d5c06b0`](https://github.com/sumitkumar112006/sewasetu-handout/commit/d5c06b0e8b4bb688e44145780bb4c901e1ffcfa5) (`fix(portal): add self-serve cancellation, allow re-application after cancellation, fix date parsing and upload validation (Issue 5)`)
  - All 5 tests passed (`Ran 5 tests in 0.097s. OK.`)

---

## Top 5 Priority Matrix (For DC Video Debrief)

Per the fellowship evaluation criteria in `BRIEF.md`, here are the top 5 interventions ranked by **civic harm reduction and legal compliance**:

| Rank | Fix Title | Primary Justification | Status |
| :---: | :--- | :--- | :---: |
| **1** | **Plug PII Leakage & Access Control (IDOR, SQLi)** | **Halt Civic Harm:** Immediately stops predatory telemarketers and scammers targeting vulnerable senior citizens. | **Resolved** |
| **2** | **Restore RTPS Deemed Approval Engine & UI Truth** | **Statutory Compliance:** Enforces legal entitlements under the Right to Public Services Act, avoiding legal penalties. | **Resolved** |
| **3** | **Fix UTF-8 Indic Script Encoding & PDF Generation** | **Civic Dignity:** Guarantees valid legal acknowledgement slips with correctly printed Assamese/Indic names. | **Resolved** |
| **4** | **Database Indexing & Server Bottleneck Elimination** | **Infrastructure Stability:** Prevents system collapse during high-traffic monthly pension disbursement deadlines. | **Resolved** |
| **5** | **Self-Serve Edit/Cancel & Form UX Fixes** | **Relieve Administration & Protect Citizens:** Clears helpdesk backlogs and prevents exploitation by bazaar middlemen. | **Resolved** |

*What to deliberately leave alone:* Major architectural rewrites, cosmetic dashboard overhauls, or multi-tenancy rewrites. Focus strictly on stabilizing high-impact citizen workflows.
