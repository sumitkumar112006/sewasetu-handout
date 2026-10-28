# Sewa Setu — Old Age Pension Portal
Government of Purvanchal, Department of Social Welfare

---

## 🌐 Live Deployed Deployment & Endpoint Directory

> **Active Public URL:** [`https://always-geography-concord-reform.trycloudflare.com`](https://always-geography-concord-reform.trycloudflare.com)  
> *Note: Tunnel connects to container port `8000`. Keep `cloudflared` running on your host machine to maintain 24/7 global access.*

### 1. Citizen & Public Services
| Page / Service | Public Live URL | Description & Access Rule |
| :--- | :--- | :--- |
| **Citizen Application** | [`/`](https://always-geography-concord-reform.trycloudflare.com/) | Public 6-step pension enrollment with phone-friendly layout. |
| **Status Portal Login** | [`/status`](https://always-geography-concord-reform.trycloudflare.com/status) | Login via Mobile + DOB (DDMMYYYY). |
| **Status & Profile View** | [`/application/1`](https://always-geography-concord-reform.trycloudflare.com/application/1) | IDOR protected (`403` for cross-user snoopers; `200` for owner/admin). |
| **Self-Serve Edit Form** | [`/application/1/edit`](https://always-geography-concord-reform.trycloudflare.com/application/1/edit) | Correct name, DOB, address, or bank details while in `PENDING` state. |
| **PDF Acknowledgement** | [`/ack/1.pdf`](https://always-geography-concord-reform.trycloudflare.com/ack/1.pdf) | Scrape protected (`403` unauthenticated; supports native Assamese/Indic fonts). |
| **Password Reset** | [`/status/reset`](https://always-geography-concord-reform.trycloudflare.com/status/reset) | Parameterized query immune to SQL injection. |
| **About the Scheme** | [`/about`](https://always-geography-concord-reform.trycloudflare.com/about) | Scheme eligibility criteria and statutory guidelines. |

### 2. Administrative & Auditor Evaluation
| Interface | Public Live URL | Default Credentials |
| :--- | :--- | :--- |
| **Admin Login** | [`/admin`](https://always-geography-concord-reform.trycloudflare.com/admin) | **Username:** `admin` <br> **Password:** `sewasetu@123` |
| **Admin Dashboard** | [`/admin/dashboard`](https://always-geography-concord-reform.trycloudflare.com/admin/dashboard) | Statutory SLA metrics, block breakdown & status counts. |
| **Applications List** | [`/admin/applications`](https://always-geography-concord-reform.trycloudflare.com/admin/applications) | Filter by `PENDING`, `APPROVED`, `DEEMED_APPROVED`, `REJECTED`. |
| **Application Review** | [`/admin/view/1`](https://always-geography-concord-reform.trycloudflare.com/admin/view/1) | Official case file inspection. |

### 3. Diagnostics & Gateway Services
| Service | Public Live URL | Purpose |
| :--- | :--- | :--- |
| **SMS Gateway Console** | [`/__gateway/`](https://always-geography-concord-reform.trycloudflare.com/__gateway/) | Real-time inspection of outbound SMS OTPs and submission receipts. |

---

## Running Locally

```bash
docker compose up -d --build
```

- Portal: http://localhost:8000
- SMS gateway console: http://localhost:8000/__gateway/
- Database: Postgres 15, seeded from `seed/seed.sql` on first boot

Listen to `dc-briefing.mp3` first (the DC's briefing), then read `BRIEF.md` and `solution.md` for complete technical audit details.   