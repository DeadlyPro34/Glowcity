from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from datetime import datetime
import os
import json
import random
import urllib.parse
import urllib.request
from werkzeug.utils import secure_filename
from datetime import timedelta
from google.oauth2 import id_token
from google.auth.transport import requests
from PIL import Image
import threading

# ---------- LOAD SECRETS FROM .env (never commit .env) ----------
def _load_env_file():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

_load_env_file()

FLASK_SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'krisha')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')

# Set ENABLE_AI=false on Render (free tier cannot run PyTorch/CLIP reliably).
ENABLE_AI = os.environ.get('ENABLE_AI', 'true').lower() in ('1', 'true', 'yes')

if not FLASK_SECRET_KEY:
    raise RuntimeError(
        'FLASK_SECRET_KEY is missing. Copy .env.example to .env and set FLASK_SECRET_KEY.'
    )

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
app.permanent_session_lifetime = timedelta(days=7)

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------- AI IMAGE DETECTION ----------
# Lazy loading the AI model to save memory/startup time
ai_pipeline = None
ai_lock = threading.Lock()

def get_ai_pipeline():
    if not ENABLE_AI:
        return None
    global ai_pipeline
    with ai_lock:
        if ai_pipeline is None:
            try:
                from transformers import pipeline
                ai_pipeline = pipeline(
                    "zero-shot-image-classification",
                    model="openai/clip-vit-base-patch32",
                )
            except Exception as e:
                print(f"AI Model Error: {e}")
                return None
    return ai_pipeline

def is_image_relevant(image_path):
    if not ENABLE_AI:
        return True, "AI skipped (cloud deploy)", 1.0
    classifier = get_ai_pipeline()
    if not classifier:
        return True, "Model Unavailable", 0.0

    # Define labels related to website features vs spam
    candidate_labels = [
        "broken streetlight",
        "pothole on road",
        "garbage or trash pile",
        "road accident",
        "broken pavement",
        "water leakage",
        "unrelated spam image",
        "meme or internet joke",
        "photo of a person",
        "photo of food",
        "random objects",
        "nature landscape",
        "certificate or document",
        "blank or empty image",
    ]
    
    try:
        results = classifier(image_path, candidate_labels=candidate_labels)
        top_result = results[0]
        
        # Labels that we consider "relevant"
        relevant_labels = [
            "broken streetlight", "pothole on road", "garbage or trash pile", 
            "road accident", "broken pavement", "water leakage", "damaged pole"
        ]
        
        # Check if the top prediction is relevant and has a decent score
        # Using a threshold to avoid weak matches
        is_relevant = top_result['label'] in relevant_labels and top_result['score'] > 0.15
        return is_relevant, top_result['label'], top_result['score']
    except Exception as e:
        print(f"Classification Error: {e}")
        return True, "Error", 0.0

# ---------- DATABASE ----------
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def create_table():
    conn = get_db_connection()

    # Complaints table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        pole_id TEXT,
        complaint_type TEXT,
        description TEXT,
        latitude TEXT,
        longitude TEXT,
        address TEXT,
        image TEXT,
        status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending', 'In Progress', 'Resolved')),
        issue_date TEXT,
        updated_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)

    # Users table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE NOT NULL,
        password TEXT
    )
    """)

    # Feedback table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        subject TEXT,
        message TEXT,
        rating INTEGER DEFAULT 0,
        submitted_at TEXT
    )
    """)
    
    # Ensure rating column exists for existing databases
    try:
        conn.execute("ALTER TABLE feedback ADD COLUMN rating INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        conn.execute("ALTER TABLE complaints ADD COLUMN address TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    conn.execute("""
    CREATE TABLE IF NOT EXISTS status_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id INTEGER NOT NULL,
        user_id INTEGER,
        status TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (complaint_id) REFERENCES complaints (id)
    )
    """)

    conn.commit()
    conn.close()

create_table()

def send_resolution_email(to_email, user_name, complaint_id, complaint_type, new_status):
    """Send email via Resend when RESEND_API_KEY is set. Returns (success, message)."""
    api_key = os.environ.get('RESEND_API_KEY')
    from_email = os.environ.get('RESEND_FROM_EMAIL', 'onboarding@resend.dev')
    if not api_key:
        return False, 'RESEND_API_KEY is not set in the environment.'
    if not to_email:
        return False, 'No recipient email on file for this user.'

    subject = f"Glowcity: Complaint #{complaint_id} is now {new_status}"
    html = f"""
    <p>Hi {user_name or 'there'},</p>
    <p>Your complaint <strong>#{complaint_id}</strong> ({complaint_type}) has been updated to
    <strong>{new_status}</strong>.</p>
    <p>Track all your reports at your Glowcity dashboard.</p>
    <p>— Glowcity Civic Team</p>
  """
    payload = json.dumps({
        'from': from_email,
        'to': [to_email],
        'subject': subject,
        'html': html,
    }).encode('utf-8')

    try:
        req = urllib.request.Request(
            'https://api.resend.com/emails',
            data=payload,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'User-Agent': 'Glowcity/1.0',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if 200 <= resp.status < 300:
                return True, f'Email sent to {to_email}.'
            return False, f'Resend returned status {resp.status}.'
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')
        print(f"Email send error ({e.code}): {body}")
        try:
            detail = json.loads(body).get('message', body)
        except json.JSONDecodeError:
            detail = body
        return False, detail
    except Exception as e:
        print(f"Email send error: {e}")
        return False, str(e)

def geocode_address(address):
    """Convert a manual address to coordinates using OpenStreetMap Nominatim."""
    try:
        params = urllib.parse.urlencode({'q': address, 'format': 'json', 'limit': 1})
        req = urllib.request.Request(
            f'https://nominatim.openstreetmap.org/search?{params}',
            headers={'User-Agent': 'Glowcity/1.0 (complaint geocoding)'}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            if data:
                return str(data[0]['lat']), str(data[0]['lon'])
    except Exception as e:
        print(f"Geocode error: {e}")
    return None, None

# ---------- CONTEXT PROCESSOR ----------
@app.context_processor
def inject_user():
    return dict(
        logged_in='user_id' in session,
        user_name=session.get('user_name'),
        admin_logged_in=session.get('admin_logged_in'),
        google_client_id=GOOGLE_CLIENT_ID,
    )

# ---------- ROUTES ----------
@app.route('/')
def home():
    return render_template('home.html')

# ---------- SUBMIT COMPLAINT ----------
@app.route('/complaint', methods=['GET', 'POST'])
def complaint():
    pole_id = request.args.get('pole_id', 'SP101')

    if request.method == 'POST':
        pole_id = request.form['pole_id']
        complaint_type = request.form['complaint_type']
        description = request.form['description']
        location_mode = request.form.get('location_mode', 'manual')
        latitude = request.form.get('latitude', '').strip()
        longitude = request.form.get('longitude', '').strip()
        address = request.form.get('address', '').strip()

        if location_mode == 'gps':
            if not latitude or not longitude:
                flash("Location unavailable. Enter address manually.", "warning")
                return redirect(url_for('complaint', pole_id=pole_id))
            address = ''
        else:
            if not address:
                flash("Please enter an address.", "warning")
                return redirect(url_for('complaint', pole_id=pole_id))
            lat, lon = geocode_address(address)
            if lat and lon:
                latitude, longitude = lat, lon
            else:
                latitude, longitude = '', ''

        image = request.files.get('image')
        filename = None

        if image and image.filename != "":
            filename = secure_filename(image.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            image.save(filepath)

            # Final check in backend for security
            is_relevant, label, score = is_image_relevant(filepath)
            if not is_relevant:
                os.remove(filepath)
                flash("Photo rejected. Upload relevant evidence.", "error")
                return redirect(url_for('complaint', pole_id=pole_id))

        issue_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_id = session.get('user_id')  # Can be None for guest reports

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO complaints
            (user_id, pole_id, complaint_type, description,
             latitude, longitude, address, image, status, issue_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, pole_id, complaint_type, description,
            latitude, longitude, address, filename, "Pending", issue_date
        ))

        conn.commit()
        conn.close()

        return redirect(url_for('success'))

    return render_template('complaint.html', pole_id=pole_id)

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/validate_image', methods=['POST'])
def validate_image_route():
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'No image uploaded'}), 400
    
    image = request.files['image']
    if image.filename == '':
        return jsonify({'success': False, 'message': 'Empty filename'}), 400

    # Check if model is still loading
    if ai_pipeline is None:
        # Try to trigger load in background or just inform user
        # We'll try to get it now, but if it takes too long, the AJAX might timeout
        # So we warn the client if it's not ready
        pass

    filename = secure_filename(image.filename)
    temp_path = os.path.join(UPLOAD_FOLDER, f"temp_{filename}")
    image.save(temp_path)
    
    is_relevant, label, score = is_image_relevant(temp_path)
    os.remove(temp_path)

    if not ENABLE_AI:
        return jsonify({
            'success': True,
            'label': label,
            'score': 1.0,
            'message': 'Photo accepted (AI validation disabled on this server).',
        })

    return jsonify({
        'success': is_relevant,
        'label': label,
        'score': float(score),
        'message': 'Image is related to website features.' if is_relevant else 'Spam image detected. Please upload image of streetlights, potholes, or garbage.'
    })

@app.route('/api/complaints')
def api_complaints():
    conn = get_db_connection()
    complaints = conn.execute("SELECT * FROM complaints").fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in complaints])

def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

def build_admin_analytics():
    conn = get_db_connection()

    total = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'").fetchone()[0]
    progress = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='In Progress'").fetchone()[0]
    resolved = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'").fetchone()[0]

    today = datetime.now().strftime("%Y-%m-%d")
    reports_today = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE issue_date LIKE ?",
        (f"{today}%",)
    ).fetchone()[0]

    type_rows = conn.execute("""
        SELECT complaint_type, COUNT(*) AS count
        FROM complaints
        GROUP BY complaint_type
        ORDER BY count DESC
    """).fetchall()

    status_rows = conn.execute("""
        SELECT status, COUNT(*) AS count
        FROM complaints
        GROUP BY status
    """).fetchall()

    heatmap_rows = conn.execute("""
        SELECT latitude, longitude, status
        FROM complaints
        WHERE latitude IS NOT NULL AND latitude != ''
          AND longitude IS NOT NULL AND longitude != ''
    """).fetchall()

    resolved_rows = conn.execute("""
        SELECT issue_date, updated_at
        FROM complaints
        WHERE status = 'Resolved' AND updated_at IS NOT NULL
    """).fetchall()

    conn.close()

    resolution_hours = []
    for row in resolved_rows:
        started = _parse_dt(row['issue_date'])
        ended = _parse_dt(row['updated_at'])
        if started and ended and ended >= started:
            resolution_hours.append((ended - started).total_seconds() / 3600)

    avg_resolution_hours = (
        round(sum(resolution_hours) / len(resolution_hours), 1)
        if resolution_hours else None
    )

    resolution_rate = round((resolved / total) * 100, 1) if total else 0

    status_weights = {'Pending': 1.0, 'In Progress': 0.7, 'Resolved': 0.35}
    heatmap = []
    for row in heatmap_rows:
        try:
            lat = float(row['latitude'])
            lng = float(row['longitude'])
            intensity = status_weights.get(row['status'], 0.6)
            heatmap.append([lat, lng, intensity])
        except (TypeError, ValueError):
            continue

    return {
        'stats': {
            'total': total,
            'pending': pending,
            'progress': progress,
            'resolved': resolved,
        },
        'reports_today': reports_today,
        'avg_resolution_hours': avg_resolution_hours,
        'resolution_rate': resolution_rate,
        'complaints_by_type': [
            {'type': r['complaint_type'] or 'Other', 'count': r['count']}
            for r in type_rows
        ],
        'status_breakdown': [
            {'status': r['status'], 'count': r['count']}
            for r in status_rows
        ],
        'heatmap': heatmap,
        'telemetry': {
            'field_teams': random.randint(8, 14),
            'response_index': random.randint(82, 98),
            'open_queue': pending + progress,
        },
        'updated_at': datetime.now().strftime("%H:%M:%S"),
    }

@app.route('/api/admin/analytics')
def api_admin_analytics():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify(build_admin_analytics())

# ---------- USER FEEDBACK ----------
@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        subject = request.form['subject']
        message = request.form['message']
        rating = request.form.get('rating', 0)
        submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO feedback (name, email, subject, message, rating, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, email, subject, message, rating, submitted_at))
        conn.commit()
        conn.close()

        flash("Thanks for your feedback!", "success")
        return redirect(url_for('success'))

    return render_template('feedback.html')

# ---------- USER AUTH ----------
@app.route('/signup', methods=['GET','POST'])
def signup():
    if 'user_id' in session:
        return redirect(url_for('my_complaints'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        try:
            cur = conn.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, password)
            )
            conn.commit()
            user_id = cur.lastrowid
            
            # Auto-login after registration
            session.permanent = True
            session['user_id'] = user_id
            session['user_name'] = name
            conn.close()
            return redirect(url_for('my_complaints'))
        except sqlite3.IntegrityError:
            conn.close()
            flash("Account already exists. Please sign in.", "warning")
            return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login')
def login():
    if 'user_id' in session:
        return redirect(url_for('my_complaints'))
    return render_template('login.html')

@app.route('/login_user', methods=['GET', 'POST'])
def login_user():
    if 'user_id' in session:
        return redirect(url_for('my_complaints'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        ).fetchone()
        conn.close()

        if user:
            session.permanent = True
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('my_complaints'))
        else:
            flash("Invalid email or password.", "error")

    return render_template('login_user.html')

@app.route('/auth/google', methods=['POST'])
def google_auth():
    token = request.json.get('id_token')
    
    try:
        # Verify the token with Google
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        
        # ID token is valid! Extract user info
        email = idinfo['email']
        name = idinfo.get('name', 'Google User')

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        
        if not user:
            cur = conn.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
            conn.commit()
            user_id = cur.lastrowid
            user_name = name
        else:
            user_id = user['id']
            user_name = user['name']
        
        conn.close()

        session.permanent = True
        session['user_id'] = user_id
        session['user_name'] = user_name
        
        return jsonify({'success': True})
    except ValueError:
        # Invalid token
        return jsonify({'success': False, 'message': 'Invalid token'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/user_logout')
def user_logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    return redirect(url_for('home'))

# ---------- USER COMPLAINT HISTORY ----------
@app.route('/my_complaints')
def my_complaints():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    complaints = conn.execute("""
        SELECT * FROM complaints
        WHERE user_id=?
        ORDER BY id DESC
    """, (session['user_id'],)).fetchall()
    conn.close()

    poll_since = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template('my_complaints.html', complaints=complaints, poll_since=poll_since)

@app.route('/api/user/status_updates')
def api_user_status_updates():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    since = request.args.get('since', '')
    since_dt = _parse_dt(since)
    if not since_dt:
        return jsonify({'updates': [], 'server_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")})

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT id, complaint_type, status, updated_at, pole_id
        FROM complaints
        WHERE user_id = ? AND updated_at IS NOT NULL AND updated_at > ?
        ORDER BY updated_at ASC
    """, (session['user_id'], since)).fetchall()
    conn.close()

    updates = []
    for row in rows:
        updates.append({
            'id': row['id'],
            'complaint_type': row['complaint_type'],
            'status': row['status'],
            'updated_at': row['updated_at'],
            'pole_id': row['pole_id'],
            'message': f"Complaint #{row['id']} ({row['complaint_type']}) is now {row['status']}.",
        })

    return jsonify({
        'updates': updates,
        'server_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })

# ---------- ADMIN LOGIN ----------
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if ADMIN_PASSWORD and username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.permanent = True
            session['admin_logged_in'] = True
            return redirect(url_for('dashboard'))
        elif not ADMIN_PASSWORD:
            flash("Admin login not configured.", "error")
        else:
            flash("Invalid admin credentials.", "error")

    return render_template('admin_login.html')

# ---------- ADMIN DASHBOARD ----------
@app.route('/dashboard')
def dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    complaints = conn.execute("SELECT * FROM complaints ORDER BY id DESC").fetchall()

    total = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'").fetchone()[0]
    progress = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='In Progress'").fetchone()[0]
    resolved = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'").fetchone()[0]

    conn.close()

    return render_template(
        'admin_dashboard.html',
        complaints=complaints,
        total=total,
        pending=pending,
        progress=progress,
        resolved=resolved
    )

# ---------- UPDATE STATUS ----------
@app.route('/update_status/<int:id>/<string:new_status>')
def update_status(id, new_status):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    updated_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    complaint = conn.execute(
        "SELECT * FROM complaints WHERE id = ?", (id,)
    ).fetchone()

    conn.execute("""
        UPDATE complaints
        SET status=?, updated_at=?
        WHERE id=?
    """, (new_status, updated_date, id))

    if complaint and complaint['user_id']:
        message = f"Complaint #{id} ({complaint['complaint_type']}) is now {new_status}."
        conn.execute("""
            INSERT INTO status_notifications
            (complaint_id, user_id, status, message, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (id, complaint['user_id'], new_status, message, updated_date))

        if new_status == 'Resolved':
            user = conn.execute(
                "SELECT name, email FROM users WHERE id = ?",
                (complaint['user_id'],)
            ).fetchone()
            if user and user['email']:
                send_resolution_email(
                    user['email'], user['name'], id,
                    complaint['complaint_type'], new_status
                )

    conn.commit()
    conn.close()

    flash(f"Status updated to {new_status}.", "success")
    return redirect(url_for('dashboard'))

# ---------- ADMIN LOGOUT ----------
@app.route('/admin_logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('home'))

# ---------- USER SETTINGS (profile route) ----------
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash("Please log in to access your profile.", "info")
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    user = conn.execute(
        "SELECT name, email FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    stats = conn.execute("""
        SELECT
            COUNT(*) AS total_filed,
            SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) AS resolved,
            SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) AS in_progress
        FROM complaints WHERE user_id = ?
    """, (user_id,)).fetchone()
    recent_complaints = conn.execute("""
        SELECT id, pole_id, complaint_type, status, issue_date, updated_at, address
        FROM complaints WHERE user_id = ?
        ORDER BY datetime(issue_date) DESC
        LIMIT 10
    """, (user_id,)).fetchall()
    conn.close()

    name = user['name'] if user else session.get('user_name', 'Citizen')
    return render_template(
        'settings.html',
        user_name=name,
        user_email=user['email'] if user else '',
        avatar_name=name.replace(' ', '+'),
        total_filed=stats['total_filed'] or 0,
        resolved=stats['resolved'] or 0,
        pending=stats['pending'] or 0,
        in_progress=stats['in_progress'] or 0,
        recent_complaints=recent_complaints,
    )

# ---------- RUN ----------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes')
    app.run(host='0.0.0.0', port=port, debug=debug)
