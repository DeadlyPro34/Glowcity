# Glowcity — Guide for Hackathon Judges

Thank you for reviewing **Glowcity**, a smart civic complaint platform. Citizens report infrastructure issues (street lights, potholes, etc.); admins review complaints, update status, and view analytics.

**Replace all placeholders** in angle brackets (e.g. `<YOUR_LIVE_URL>`) before sharing this file with organizers.

---

## Quick links

| Item | Value |
|------|--------|
| **Live demo** | `<YOUR_LIVE_URL>` (e.g. `https://glowcity.onrender.com`) |
| **GitHub repository** | `<YOUR_GITHUB_REPO_URL>` (e.g. `https://github.com/YOUR_USERNAME/Glowcity`) |
| **Admin username** | `<ADMIN_USERNAME>` (default on Render: `admin`) |
| **Admin password** | `<ADMIN_PASSWORD>` *(share privately with organizers, not in public README)* |

---

## Important notes (read first)

1. **Free hosting (Render)** — The live demo may **sleep** after ~15 minutes of no traffic. The **first visit** after sleep can take **30–60 seconds** to load. Refresh once if the page is blank or slow.

2. **AI photo validation on live demo** — On the hosted version, `ENABLE_AI=false` (required on Render’s free tier). Complaints with photos still work; the app **skips** CLIP/PyTorch image checks. This is expected, not a bug.

3. **Full AI locally** — Judges who clone the repo and run locally with `ENABLE_AI=true` get AI photo relevance checking (first upload may download the CLIP model; allow a few minutes).

4. **Demo data** — The hosted app uses SQLite on **ephemeral disk**. Complaints and uploads may **reset** when the service redeploys or restarts. Fine for demos; use local run for persistent testing.

5. **Google Sign-In** — Works on the live site only if the team configured `GOOGLE_CLIENT_ID` with the correct Render URL in Google Cloud Console. **Email sign-up / sign-in always works** without Google.

6. **Resolution emails** — Optional. If `RESEND_API_KEY` is not set on the host, marking a complaint “Resolved” still works; email is simply not sent.

---

## Option 1 — Live demo (recommended, no install)

Best for a quick walkthrough. No Python or Git required.

### Open the site

1. Go to: **<YOUR_LIVE_URL>**
2. If the page is slow or times out, wait up to **60 seconds** and refresh (free tier wake-up).

### Citizen flow (report a complaint)

1. Open **<YOUR_LIVE_URL>/login**
2. Click **Continue as Citizen**
3. **Sign up** (email + password) or **Sign in with Google** (if enabled)
4. From the citizen dashboard, **file a new complaint**:
   - Choose issue type (e.g. street light, pothole)
   - Add description, address or GPS, and optional photo
5. Open **My complaints** to see status updates (toasts may appear when admin changes status)

### Admin flow (manage complaints)

1. Open **<YOUR_LIVE_URL>/login** → **Continue as Admin**  
   Or go directly to **<YOUR_LIVE_URL>/admin**
2. Sign in:
   - **Username:** `<ADMIN_USERNAME>`
   - **Password:** `<ADMIN_PASSWORD>`
3. On the **dashboard** you can:
   - View all complaints
   - Change status: **Pending** → **In Progress** → **Resolved**
   - Use analytics / heatmap (if present in your build)

### URLs reference (live)

| Page | Path |
|------|------|
| Home | `/` |
| Login (citizen / admin choice) | `/login` |
| Citizen sign-in | `/login` → Continue as Citizen |
| Citizen sign-up | `/signup` |
| Admin login | `/admin` |
| Admin dashboard | `/dashboard` |

---

## Option 2 — Run locally (full features + AI)

Use this if you want **AI photo validation**, offline development, or persistent local data.

### Prerequisites

- **Python 3.11+** (3.12 recommended)
- **Git**
- **Internet** (first photo validation downloads the CLIP model, ~350–600 MB cache under `%USERPROFILE%\.cache\huggingface` on Windows)

### Steps (Windows PowerShell)

```powershell
git clone <YOUR_GITHUB_REPO_URL>
cd Glowcity

copy .env.example .env
```

Edit `.env` and set at least:

```env
FLASK_SECRET_KEY=<long-random-string>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<choose-a-password>
ENABLE_AI=true
```

Optional:

```env
GOOGLE_CLIENT_ID=<your-client-id.apps.googleusercontent.com>
RESEND_API_KEY=
RESEND_FROM_EMAIL=onboarding@resend.dev
```

Create virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

**Optional — smaller CPU-only PyTorch** (saves disk space):

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

Run the app:

```powershell
python app.py
```

Open in browser: **http://127.0.0.1:5000**

### Local login (same as hosted)

| Role | How to access | Credentials |
|------|----------------|-------------|
| **Citizen** | `/login` → Continue as Citizen | Sign up with email, or Google if `GOOGLE_CLIENT_ID` is set in `.env` |
| **Admin** | `/login` → Continue as Admin, or `/admin` | Username/password from `.env` (`ADMIN_USERNAME` / `ADMIN_PASSWORD`) |

### Local URLs reference

Same paths as the live demo table above, on `http://127.0.0.1:5000`.

---

## Option 3 — Deploy yourself (optional, for technical judges)

The repo includes `render.yaml` for [Render](https://render.com) (free tier).

1. Fork or clone **<YOUR_GITHUB_REPO_URL>**
2. Render → **New** → **Blueprint** → select the repo
3. Set environment variables (see team’s `README.md` → “Deploy on Render”)
4. Required for admin: `ADMIN_PASSWORD`, `FLASK_SECRET_KEY`, `ENABLE_AI=false` on free tier

---

## Feature overview

| Feature | Live demo (Render) | Local (`ENABLE_AI=true`) |
|---------|--------------------|---------------------------|
| Citizen sign-up / sign-in (email) | Yes | Yes |
| Google Sign-In | If team configured | If `GOOGLE_CLIENT_ID` in `.env` |
| File complaint (text, address, GPS, photo) | Yes | Yes |
| AI photo relevance check | No (disabled) | Yes (first run may download model) |
| Citizen dashboard & my complaints | Yes | Yes |
| Real-time status notifications | Yes | Yes |
| Admin dashboard & status updates | Yes | Yes |
| Analytics / heatmap | Yes | Yes |
| Email on “Resolved” (Resend) | Only if `RESEND_API_KEY` set | Only if configured in `.env` |

---

## Troubleshooting

| Issue | What to do |
|-------|------------|
| Live site very slow or blank | Wait 30–60 s, refresh; free tier may be waking up |
| `FLASK_SECRET_KEY is missing` (local) | Copy `.env.example` → `.env` and set `FLASK_SECRET_KEY` |
| Admin: “not configured” | Host missing `ADMIN_PASSWORD` — contact team |
| Admin: “Invalid credentials” | Use exact `ADMIN_USERNAME` / `ADMIN_PASSWORD` from team |
| Google button missing or error | Team may not have set `GOOGLE_CLIENT_ID`; use email sign-up |
| Slow first photo upload (local) | CLIP model downloading; wait once |
| Huge clone / install size | Do not commit `.venv`; only `pip install -r requirements.txt` |

---

## Project structure (for reviewers)

| Path | Purpose |
|------|---------|
| `app.py` | Flask app, routes, auth, complaints |
| `templates/` | HTML pages |
| `static/` | CSS, uploads folder |
| `requirements.txt` | Local/full dependencies (includes AI stack) |
| `requirements-render.txt` | Hosted deploy (no PyTorch) |
| `render.yaml` | Render Blueprint config |
| `.env.example` | Environment variable template |

---

## Contact / team

- **Team name:** `<YOUR_TEAM_NAME>`
- **Contact:** `<YOUR_EMAIL_OR_DISCORD>`

---

*Hackathon submission — update placeholders before sharing with judges.*
