# Glowcity

Smart civic complaint platform — citizens report infrastructure issues (street lights, potholes, etc.); admins manage status and analytics.

**Hackathon judges:** see **[JUDGES.md](JUDGES.md)** for live demo URL, admin login, local run steps, and feature notes.

## Project size (why the folder looks huge)

| What | Approx. size |
|------|----------------|
| **Source code** (templates, `app.py`, CSS, DB) | **~5 MB** |
| **`.venv`** (PyTorch + Transformers for AI photo check) | **~800 MB** |
| **CLIP model cache** (first run, often under `%USERPROFILE%\.cache\huggingface`) | **~350–600 MB** |

The app itself is small. The large footprint is **normal** for local ML: PyTorch alone is often 500 MB+.

**For hackathon submission / GitHub:** commit only source files. Do **not** zip or upload `.venv`. Judges run `pip install -r requirements.txt` on their machine.

## Setup

### 1. Prerequisites

- Python 3.11+ (3.12 recommended)
- Git (optional)

### 2. Clone and configure

```bash
cd Glowcity
copy .env.example .env
```

Edit `.env` and set at least `FLASK_SECRET_KEY`. Add `GOOGLE_CLIENT_ID`, `ADMIN_PASSWORD`, and optional `RESEND_*` keys as needed.

### 3. Virtual environment and dependencies

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

**Smaller PyTorch (CPU only, optional):**

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

The first complaint with photo validation downloads the CLIP model (`openai/clip-vit-base-patch32`). Allow a few minutes and stable internet.

### 4. Run

```powershell
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

- **Citizen flow:** `/login` → Continue as Citizen → sign in / sign up  
- **Admin flow:** `/login` → Continue as Admin  

## What not to commit

See `.gitignore`. In particular:

- `.env` (secrets)
- `.venv/` (recreated with `pip install`)
- `database.db` (local SQLite)
- `static/uploads/` (user photos)

## Features (overview)

- Complaint filing with address or GPS + AI image relevance check
- Citizen dashboard and real-time status toasts
- Admin dashboard with analytics, heatmap, and status updates
- Optional email on “Resolved” via Resend

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `FLASK_SECRET_KEY is missing` | Copy `.env.example` → `.env` and set the key |
| Slow first photo upload | CLIP model is downloading; wait once |
| Disk space | Delete `.venv` and reinstall only when needed; HF cache is in `%USERPROFILE%\.cache\huggingface` |

## Deploy on Render (free)

The **free** Render web service can run Glowcity, but **not** with local PyTorch/CLIP (needs ~800MB+ RAM). On Render we set `ENABLE_AI=false`: complaints, admin dashboard, maps, and auth still work; photo AI validation is skipped (same as “model unavailable” fallback).

### Step 1 — Push to GitHub

Upload the repo **without** `.venv`, `.env`, or `database.db` (see `.gitignore`).

### Step 2 — Create Render service

1. Go to [render.com](https://render.com) → sign up (free).
2. **New** → **Blueprint** → connect your GitHub repo (or **Web Service** manually).
3. If using `render.yaml` in the repo, Render reads build/start commands automatically.
4. If manual:
   - **Build command:** `pip install --upgrade pip && pip install -r requirements-render.txt`
   - **Start command:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`
   - **Plan:** Free

### Step 3 — Environment variables (Render dashboard → Environment)

| Variable | Required | Notes |
|----------|----------|--------|
| `FLASK_SECRET_KEY` | Yes | Long random string (Render can auto-generate) |
| `ADMIN_PASSWORD` | Yes | Admin login password for judges |
| `ADMIN_USERNAME` | Optional | Default `admin` in `render.yaml` |
| `ENABLE_AI` | Yes on free | Set to `false` |
| `GOOGLE_CLIENT_ID` | Optional | For Google sign-in |
| `RESEND_API_KEY` | Optional | Resolution emails |

Do **not** upload `.env` — paste secrets only in Render’s UI.

### Step 4 — Google Sign-In (if used)

In [Google Cloud Console](https://console.cloud.google.com/) → OAuth client → add:

- **Authorized JavaScript origins:** `https://YOUR-SERVICE.onrender.com`
- **Authorized redirect URIs:** same URL if required by your client type

### Step 5 — Share the live URL

After deploy, Render gives a URL like `https://glowcity-xxxx.onrender.com`. Put it in your hackathon README for judges.

**Free tier notes:**

- Service **sleeps** after ~15 min idle; first visit may take **30–60 seconds** to wake up.
- SQLite and uploads live on **ephemeral disk** — data may reset on redeploy (fine for demos).
- For **full AI** locally: `ENABLE_AI=true` and `pip install -r requirements-ai.txt`.

## License

Hackathon / academic use — update as required by your team.
