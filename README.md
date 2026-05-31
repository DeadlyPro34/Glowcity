# Glowcity

**Smart civic complaint platform** — citizens report infrastructure issues (street lights, potholes, broken signals, etc.); city admins review complaints, update status, and view analytics on a live dashboard.

| | |
|---|---|
| **Live demo** | [https://glowcity-uygw.onrender.com](https://glowcity-uygw.onrender.com) |
| **Judge guide** | [JUDGES.md](JUDGES.md) — login credentials, testing steps, troubleshooting |
| **Team** | GlowGuardian |
| **Contact** | krishakalal2713@gmail.com |

> **First visit slow?** The free Render tier sleeps after ~15 min idle; the first load may take **30–60 seconds**. Refresh once if needed.

---

## Problem & solution

Civic infrastructure problems are often reported through scattered channels, with little visibility for citizens on whether anything was done.

**Glowcity** gives citizens a single place to file complaints (with location and photos), track status in real time, and gives admins a dashboard to prioritize work, update statuses, and see heatmap-style analytics.

---

## Features

| Area | Capabilities |
|------|----------------|
| **Citizens** | Sign up / sign in (email or Google), file complaints with type, description, address or GPS, optional photo |
| **AI (local)** | CLIP-based check that uploaded photos match the complaint category (`ENABLE_AI=true`) |
| **Tracking** | “My complaints” dashboard and live status toasts when admins update a ticket |
| **Admins** | Secure login, complaint list, status workflow (Pending → In Progress → Resolved), analytics API |
| **Optional** | Resolution emails via [Resend](https://resend.com) when `RESEND_API_KEY` is set |

**Live demo note:** AI photo validation is **disabled** on Render (`ENABLE_AI=false`) due to free-tier memory limits. All other features work on the hosted site.

---

## Tech stack

- **Backend:** Python 3.12, Flask, SQLite, Gunicorn (production)
- **Auth:** Session-based admin login; citizen email/password + optional Google Sign-In
- **AI (local only):** PyTorch, Hugging Face Transformers, OpenAI CLIP (`openai/clip-vit-base-patch32`)
- **Frontend:** HTML templates, Tailwind (CDN), custom CSS

---

## Quick start (local development)

### Prerequisites

- Python **3.11+** (3.12 recommended)
- Git

### 1. Clone and configure

```powershell
git clone https://github.com/krisha-kalal/Glowcity.git
cd Glowcity
copy .env.example .env
```

Edit `.env` — minimum required:

```env
FLASK_SECRET_KEY=your-long-random-secret
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-admin-password
ENABLE_AI=true
```

Optional: `GOOGLE_CLIENT_ID`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL` (see [.env.example](.env.example)).

### 2. Install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

**Smaller install (CPU-only PyTorch, optional):**

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

The first complaint with photo validation downloads the CLIP model (~350–600 MB cache, often under `%USERPROFILE%\.cache\huggingface` on Windows). Allow a few minutes on first use.

### 3. Run

```powershell
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

| Role | Path |
|------|------|
| Home | `/` |
| Login hub | `/login` |
| Citizen sign-in / sign-up | `/login` → Citizen, or `/signup` |
| File complaint | `/complaint` |
| Admin | `/admin` → dashboard at `/dashboard` |

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FLASK_SECRET_KEY` | Yes | Flask session signing |
| `ADMIN_USERNAME` | Yes (admin) | Admin login username (default in code: `krisha`; Render uses `admin`) |
| `ADMIN_PASSWORD` | Yes (admin) | Admin login password |
| `ENABLE_AI` | Recommended | `true` locally for photo AI; `false` on Render free tier |
| `GOOGLE_CLIENT_ID` | Optional | Google Sign-In for citizens |
| `RESEND_API_KEY` | Optional | Send email when status is Resolved |
| `RESEND_FROM_EMAIL` | Optional | From address for Resend |
| `FLASK_DEBUG` | Optional | `true` for local debug (use `false` in production) |
| `PORT` | Auto on Render | Set by host; default `5000` locally |

Never commit `.env` — use `.env.example` as a template.

---

## Deploy on Render (free tier)

This repo includes [`render.yaml`](render.yaml) for one-click **Blueprint** deploy.

1. Push this repo to GitHub (no `.venv`, `.env`, or `database.db`).
2. [Render](https://render.com) → **New** → **Blueprint** → connect **Glowcity**.
3. Set **`ADMIN_PASSWORD`** when prompted (must match what you publish for judges if using [JUDGES.md](JUDGES.md)).
4. After deploy, your URL will look like `https://glowcity-xxxx.onrender.com`.

**Render environment (required on free plan):**

| Variable | Value |
|----------|--------|
| `ENABLE_AI` | `false` |
| `FLASK_SECRET_KEY` | Auto-generate or long random string |
| `ADMIN_USERNAME` | `admin` |
| `ADMIN_PASSWORD` | Your chosen password |

**Google Sign-In on Render:** In [Google Cloud Console](https://console.cloud.google.com/), add your Render URL to **Authorized JavaScript origins** (e.g. `https://glowcity-uygw.onrender.com`, no trailing slash).

**Free tier limits:** Ephemeral SQLite/uploads (data may reset on redeploy); no PyTorch on 512 MB RAM.

Manual service settings (if not using Blueprint):

- **Build:** `pip install --upgrade pip && pip install -r requirements-render.txt`
- **Start:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`

---

## Project structure

```
Glowcity/
├── app.py                 # Flask routes, auth, complaints, AI hook
├── templates/             # HTML pages
├── static/                # CSS, uploaded images
├── requirements.txt       # Local dev (web + AI)
├── requirements-render.txt
├── requirements-ai.txt
├── render.yaml            # Render Blueprint
├── .env.example
├── JUDGES.md              # Hackathon judge instructions
└── README.md
```

---

## Repository size (why the folder can look huge locally)

| What | Approx. size |
|------|----------------|
| Source code | ~5 MB |
| `.venv` (PyTorch + Transformers) | ~800 MB |
| Hugging Face CLIP cache (first run) | ~350–600 MB |

**For GitHub:** only commit source. Recreate `.venv` with `pip install -r requirements.txt`. See [.gitignore](.gitignore).

---

## What not to commit

- `.env` (secrets)
- `.venv/` / `venv/`
- `database.db` (local SQLite)
- `static/uploads/*` (user-uploaded photos)

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `FLASK_SECRET_KEY is missing` | Copy `.env.example` → `.env` and set the key |
| Admin login fails on Render | Match `ADMIN_USERNAME` / `ADMIN_PASSWORD` in Render Environment with [JUDGES.md](JUDGES.md) |
| Slow first photo upload (local) | CLIP model downloading; wait once |
| Live site blank / slow | Render waking from sleep; wait 30–60 s and refresh |
| Google Sign-In error | Add exact `https://your-app.onrender.com` to OAuth origins |

More detail for reviewers: **[JUDGES.md](JUDGES.md)**.

---

## Hackathon submission

- **Demo:** [https://glowcity-uygw.onrender.com](https://glowcity-uygw.onrender.com)
- **Repo:** [https://github.com/krisha-kalal/Glowcity](https://github.com/krisha-kalal/Glowcity)
- **Judges:** [JUDGES.md](JUDGES.md) (admin login, flows, live vs local features)

---

## License

Hackathon / academic use — update as required by your team.
