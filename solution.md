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

---

## 2. Broken RTPS "Deemed Approval" Automation Engine

### 1. What Happened to the Citizens (The Real-World Symptom)
Under the *Purvanchal Right to Public Services (RTPS) Act*, if an application is untouched for >15 days, it must automatically become `DEEMED_APPROVED`. This automated overnight job abruptly stopped working around Holi (March 2026). Overdue files stay stuck in `PENDING` indefinitely, denying senior citizens their monthly pension.

### 2. Why Did This Happen? (The Exact Code Bugs)

* **Bug A — Broken Config Path in `app/scripts/deemed_approval.py:22-25`:**
  ```python
  config = configparser.ConfigParser()
  CONFIG_PATH = os.path.join(BASE_DIR, "config", "settings.ini")
  with open(CONFIG_PATH) as fh:
      config.read_file(fh)
  ```
  * **Root Cause:** In March 2026, the configuration file was renamed from `settings.ini` to `app.ini` (noted in `app/config/app.ini:2`). The cron script was never updated. Every night at 02:00 AM, cron executes the script and immediately crashes with `FileNotFoundError: config/settings.ini`.

* **Bug B — Static Status Display in `app/app.py:413-420`:**
  * **Root Cause:** The citizen status portal blindly reads whatever static string is in the database `status` column. When the batch job fails, citizens still see `PENDING` even after 30+ days, violating their statutory rights.

### 3. How We Solve It (Solution Approach)
1. **Fix the Config Path:** Point `CONFIG_PATH` to `app.ini` in `app/scripts/deemed_approval.py`.
   ```python
   CONFIG_PATH = os.path.join(BASE_DIR, "config", "app.ini")
   ```
2. **Dynamic UI Fallback (Statutory Truth):** In `app/app.py` (`view_application`), if an application is `PENDING` and `(now - submitted_at) > 15 days`, dynamically display `DEEMED APPROVED (RTPS Statutory)` so citizens are protected even if a batch run lags.
   ```python
   if status == 'PENDING' and submitted_at and (datetime.now() - submitted_at).days > 15:
       status = 'DEEMED_APPROVED'
   ```

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

### 3. How We Solve It (Solution Approach)
1. **Enforce Ownership on Citizen Routes:** Check that the application belongs to `session['portal_mobile']` (or user is admin) before returning PDF or application details.
   ```python
   if not session.get("admin") and row['mobile'] != session.get("portal_mobile"):
       abort(403)
   ```
2. **Enforce Strict Admin Check:** Change approval/rejection checks to `if not session.get("admin"): abort(403)`.
3. **Use Parameterized Queries:** Prevent SQL injection with `cur.execute("SELECT mobile FROM portal_users WHERE mobile = %s", (mobile,))`.
4. **Externalize Hardcoded Secrets:** Move hardcoded credentials (`sewasetu@123`, `ssp-prod-key-2023-donotshare`) to environment variables.

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

---

## 5. Absence of Application Editing / Cancellation Flow (Helpdesk Lockout)

### 1. What Happened to the Citizens (The Real-World Symptom)
Elderly citizens making minor typos (e.g. misspelling a name or single digit error in IFSC/bank account) have no option to edit or cancel. The portal blocks them from submitting a new application, swamping the district helpdesk with manual record deletion requests.

### 2. Why Did This Happen? (The Exact Code Bugs)

* **Bug A — Strict Duplicate Lockout in `app/app.py:297-302`:**
  ```python
  cur.execute("SELECT count(*) FROM applications WHERE mobile = %s", (mobile,))
  if cur.fetchone()[0] > 0:
      flash("An application already exists for this mobile number. Duplicate applications are not permitted.")
      return redirect(url_for("index"))
  ```
  * **Root Cause:** It counts all records for that phone number regardless of status. Even if a citizen made a mistake and wants to cancel, the system permanently locks that phone number from re-applying.

* **Bug B — One-Way Final Pipeline in `app/app.py:305-315`:**
  * **Root Cause:** Form data is committed directly into immutable `PENDING` state with no pre-submission review step, no draft state, and no cancellation endpoint.

### 3. How We Solve It (Solution Approach)
1. **Add Self-Serve Cancellation:** In the citizen portal (`/application/<id>`), provide a "Cancel Application" button while status is `PENDING`. Clicking it marks status as `CANCELLED`.
2. **Ignore Cancelled Records in Duplicate Check:**
   ```python
   cur.execute(
       "SELECT count(*) FROM applications WHERE mobile = %s AND status NOT IN ('CANCELLED', 'REJECTED')",
       (mobile,)
   )
   ```
3. **Add Pre-Submission Confirmation:** Show an overview of entered details before final submission so seniors or village volunteers can catch typos before submitting.

---

## 6. Exclusionary UX, Illogical Validation & Middleman Exploitation

### 1. What Happened to the Citizens (The Real-World Symptom)
Eligible seniors fail to complete the form independently because of confusing validation errors and broken date parsing. Exploitative middlemen in local bazaars take advantage by charging high illegal fees to submit forms for citizens.

### 2. Why Did This Happen? (The Exact Code Bugs)

* **Bug A — Inverted US vs UK Date Parsing in `app/app.py:272-282`:**
  ```python
  # Form requests DD/MM/YYYY, but code checks US format (%m/%d/%Y) first!
  for fmt in ("%m/%d/%Y", "%d/%m/%Y"):
      try:
          dob = datetime.strptime(dob_raw, fmt).date()
          break
      except ValueError:
          continue
  ```
  * **Root Cause:** If a senior born on 5th June 1950 inputs `05/06/1950`, `%m/%d/%Y` matches first and parses it as May 6, 1950. The portal password is generated on Line 318 as `06051950`. The citizen tries to log in with their actual date of birth (`05061950`) and is permanently locked out!

* **Bug B — Mandatory Employer for Widows in `app/app.py:267-270`:**
  ```python
  if marital == "Widowed":
      if not husband_name or not husband_employer:
          flash("Something went wrong. Please try again.")
          return redirect(url_for("form_step", step=1))
  ```
  * **Root Cause:** If marital status is "Widowed", the system mandates "Husband's Current Employer". A widow whose husband is deceased cannot provide a current employer, and the system fails with an unhelpful error.

* **Bug C — Misleading File Upload Constraints in `app/app.py:215-226` vs `app/templates/upload.html:6`:**
  ```python
  if not filename.endswith(".pdf"):
      flash("ERR_VAL_47")
  if len(content) > 102400:
      flash("ERR_VAL_47")
  ```
  * **Root Cause:** The UI says *"Accepted formats: JPG or PDF, maximum size 5 MB"*. But the backend strictly rejects JPGs (`if not filename.endswith(".pdf")`), caps the size at 100 KB (`102400`), and throws cryptic code `ERR_VAL_47`.

### 3. How We Solve It (Solution Approach)
1. **Prioritize Indian Date Format:** Swap parsing order to check `"%d/%m/%Y"` before `"%m/%d/%Y"`.
2. **Remove Illogical Widow Requirement:** Do not require `husband_employer` when `marital == "Widowed"`.
3. **Align Upload Constraints with UI:** Accept `.pdf`, `.jpg`, and `.jpeg` up to 5 MB (`5 * 1024 * 1024`) and display clear error messages instead of `ERR_VAL_47`.
   ```python
   allowed = (".pdf", ".jpg", ".jpeg")
   if not any(filename.endswith(ext) for ext in allowed):
       flash("Please upload your document in PDF or JPG format.")
   if len(content) > 5 * 1024 * 1024:
       flash("Uploaded document must be under 5 MB.")
   ```

---

## Top 5 Priority Matrix (For DC Video Debrief)

Per the fellowship evaluation criteria in `BRIEF.md`, here are the top 5 interventions ranked by **civic harm reduction and legal compliance**:

| Rank | Fix Title | Primary Justification |
| :---: | :--- | :--- |
| **1** | **Plug PII Leakage & Access Control (IDOR, SQLi)** | **Halt Civic Harm:** Immediately stops predatory telemarketers and scammers targeting vulnerable senior citizens. |
| **2** | **Restore RTPS Deemed Approval Engine & UI Truth** | **Statutory Compliance:** Enforces legal entitlements under the Right to Public Services Act, avoiding legal penalties. |
| **3** | **Fix UTF-8 Indic Script Encoding & PDF Generation** | **Civic Dignity:** Guarantees valid legal acknowledgement slips with correctly printed Assamese/Indic names. |
| **4** | **Database Indexing & Server Bottleneck Elimination** | **Infrastructure Stability:** Prevents system collapse during high-traffic monthly pension disbursement deadlines. |
| **5** | **Self-Serve Edit/Cancel & Form UX Fixes** | **Relieve Administration & Protect Citizens:** Clears helpdesk backlogs and prevents exploitation by bazaar middlemen. |

*What to deliberately leave alone:* Major architectural rewrites, cosmetic dashboard overhauls, or multi-tenancy rewrites. Focus strictly on stabilizing high-impact citizen workflows.
