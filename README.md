# Sewa Setu — Old Age Pension Portal

Handover copy. Vendor maintenance contract ended 31/01/2026.

## Running

```
docker compose up --build
```

- Portal: http://localhost:8000
- SMS gateway console (simulated telecom): http://localhost:8000/__gateway/ —
  "sent" OTPs appear here once delivered. The gateway runs on the internal
  network and is served through the portal, so only one port is exposed.
- Database: Postgres, loaded from `seed/seed.sql` on first boot

Production server logs (Jan–Jun 2026) are provided in `logs/`.

Listen to `dc-briefing.mp3` first (the DC's briefing), then read `BRIEF.md`.




Audio recording mein Deputy Commissioner dwara batayi gayi sabhi actual problems ke core technical aur operational keywords ye rahe:   Character Encoding / UTF-8 Corruption (???? & Name Truncation): Assamese script acknowledgement slip par question marks (????) ban jana aur lambe naam beech me se cut ho jana.   Application Edit/Cancel Lockout (Helpdesk Overflow): Form submit hone ke baad minor typing mistake theek karne ya cancel karne ka koi option na hona, jisse helpdesk par manual deletion requests ka flood aana.   Broken RTPS "Deemed Approval" Automation: Right to Public Services (RTPS) act ke tehat 15 din tak pending rehne wali files ka automatically 'Deemed Approved' hone wala overnight scheduled job Holi ke aas-paas se band ho jana.   Cyclical Pre-Disbursement Server Freeze (Downtime / Latency): Har mahine pension disbursement deadline se 2–3 din pehle portal ka poori tarah crawl / slow ho jana.   PII Data Leakage / Privacy Breach: Application submit hote hi elderly citizens ka data bahar leak hona aur unhe unsolicited sales calls/visits aana.   Hostile Digital UI / Middleman Exploitation: Complex digital form ki wajah se eligible buzurgon ka khud form na bhar pana aur bazaar ke middlemen dwara paise lekar form fill kiya jana.   