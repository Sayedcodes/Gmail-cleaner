
import json
import os
import threading
import time
import uuid
from functools import wraps

os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from flask import Flask, jsonify, redirect, render_template_string, request, session, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import BatchHttpRequest
from werkzeug.middleware.proxy_fix import ProxyFix


SCOPES = ["https://mail.google.com/"]
JOBS = {}
JOBS_LOCK = threading.Lock()

CATEGORIES = {
    "promotions": {
        "label": "Promotions",
        "query": "category:promotions OR label:promotions",
    },
    "newsletters": {
        "label": "Newsletters",
        "query": (
            "unsubscribe OR from:newsletter OR from:noreply OR from:no-reply "
            "OR subject:newsletter OR subject:digest OR subject:weekly"
        ),
    },
    "jobs": {
        "label": "Job Emails",
        "query": (
            "from:indeed.com OR from:linkedin.com OR from:shine.com "
            "OR from:internshala.com OR from:naukri.com "
            "OR subject:\"job alert\" OR subject:hiring OR subject:openings"
        ),
    },
    "social": {
        "label": "Social Notifications",
        "query": (
            "category:social OR from:notifications OR from:noreply@linkedin.com "
            "OR from:twitter OR from:facebook"
        ),
    },
    "orders": {
        "label": "Orders & Receipts",
        "query": (
            "subject:order OR subject:receipt OR subject:invoice "
            "OR subject:payment OR subject:\"your purchase\""
        ),
    },
    "spam": {
        "label": "Spam",
        "query": "in:spam",
    },
}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


BASE_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gmail Cleaner</title>
  <style>
    body {
      margin: 0;
      font-family: Arial, Segoe UI, sans-serif;
      background: #0f1117;
      color: #f5f5f5;
      padding: 24px;
    }
    .box {
      max-width: 900px;
      margin: 0 auto 18px;
      background: #171a23;
      border: 1px solid #2b3242;
      border-radius: 18px;
      padding: 22px;
      box-shadow: 0 18px 45px #0006;
    }
    h1 { margin: 0; font-size: 34px; }
    h2 { margin-top: 0; }
    p { color: #b9c0d0; line-height: 1.55; }
    .btn {
      display: inline-block;
      border: 0;
      border-radius: 12px;
      padding: 12px 16px;
      background: #8b5cf6;
      color: white;
      text-decoration: none;
      font-weight: 700;
      cursor: pointer;
      margin: 4px 6px 4px 0;
    }
    .btn2 { background: #252b3b; }
    .danger { background: #ef4444; }
    .ok { background: #22c55e; color: #07130b; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
    }
    .opt {
      background: #202637;
      border: 1px solid #343b4e;
      border-radius: 13px;
      padding: 13px;
      display: flex;
      gap: 10px;
      align-items: center;
    }
    input, textarea {
      width: 100%;
      box-sizing: border-box;
      margin-top: 7px;
      background: #0c101a;
      color: white;
      border: 1px solid #343b4e;
      border-radius: 10px;
      padding: 11px;
    }
    input[type=checkbox], input[type=radio] {
      width: auto;
      margin: 0;
    }
    code {
      white-space: pre-wrap;
      display: block;
      background: #0b0f18;
      border: 1px solid #343b4e;
      border-radius: 10px;
      padding: 12px;
      overflow-wrap: anywhere;
    }
    .msg {
      max-width: 900px;
      margin: 0 auto 18px;
      border-radius: 14px;
      padding: 14px;
      background: #121827;
      border-left: 4px solid #8b5cf6;
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .progress-shell {
      background: #070b13;
      border: 1px solid #343b4e;
      border-radius: 999px;
      overflow: hidden;
      height: 32px;
      position: relative;
      margin: 16px 0;
    }
    .progress-fill {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #16a34a, #39ff14);
      transition: width .4s ease;
    }
    .progress-label {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      color: #f7fee7;
      text-shadow: 0 1px 4px #000;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
      gap: 10px;
      margin-top: 12px;
    }
    .stat {
      background: #202637;
      border: 1px solid #343b4e;
      border-radius: 13px;
      padding: 12px;
    }
    .stat span {
      color: #b9c0d0;
      display: block;
      font-size: 13px;
    }
    .stat b {
      display: block;
      font-size: 23px;
      margin-top: 6px;
    }
    .terminal {
      background: #020617;
      color: #39ff14;
      border: 1px solid #1f2937;
      border-radius: 12px;
      padding: 14px;
      margin-top: 14px;
      font-family: Consolas, Monaco, monospace;
      min-height: 54px;
      line-height: 1.45;
    }
    @media(max-width:700px) {
      .row { grid-template-columns: 1fr; }
      body { padding: 12px; }
    }
  </style>
</head>
<body>
  {% if msg %}
    <div class="msg">{{ msg }}</div>
  {% endif %}

  <div class="box">
    <h1>Gmail Cleaner</h1>
    <p>Emails permanently delete nahi honge, sirf Gmail Trash me move honge.</p>
    {% if email %}
      <p>
        Logged in: <b>{{ email }}</b>
        <a class="btn btn2" href="{{ url_for('logout') }}">Logout</a>
      </p>
    {% endif %}
  </div>

  {{ body | safe }}
</body>
</html>
"""


def render_page(body_template, msg=None, **context):
    body = render_template_string(body_template, **context)
    return render_template_string(
        BASE_HTML,
        body=body,
        email=session.get("email"),
        msg=msg,
    )


def base_url():
    configured_url = (
        os.environ.get("PUBLIC_BASE_URL")
        or os.environ.get("RENDER_EXTERNAL_URL")
        or request.host_url
    )
    return configured_url.rstrip("/")


def callback_url():
    return base_url() + "/callback"


def client_config():
    raw = os.environ.get("GOOGLE_CREDENTIALS_JSON", "").strip()

    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "GOOGLE_CREDENTIALS_JSON valid JSON nahi hai. "
                "credentials.json ka full content paste karo."
            ) from exc

    if os.path.exists("credentials.json"):
        with open("credentials.json", "r", encoding="utf-8") as file:
            return json.load(file)

    raise RuntimeError(
        "GOOGLE_CREDENTIALS_JSON missing hai. Render Environment me credentials.json ka full content paste karo."
    )


def allowed_emails():
    raw = os.environ.get("ALLOWED_EMAILS", "").strip().lower()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def credentials_to_dict(credentials):
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }


def credentials_from_info(info):
    credentials = Credentials.from_authorized_user_info(info, SCOPES)

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    return credentials


def credentials_from_session():
    info = session.get("credentials")
    if not info:
        raise RuntimeError("Login required")

    credentials = credentials_from_info(info)
    session["credentials"] = credentials_to_dict(credentials)
    return credentials


def gmail_service():
    return build("gmail", "v1", credentials=credentials_from_session(), cache_discovery=False)


def gmail_service_from_info(info):
    return build("gmail", "v1", credentials=credentials_from_info(info), cache_discovery=False)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "credentials" not in session:
            return redirect(url_for("home"))
        return fn(*args, **kwargs)

    return wrapper


def make_query(form):
    parts = []
    labels = []

    for key in form.getlist("category"):
        if key in CATEGORIES:
            labels.append(CATEGORIES[key]["label"])
            parts.append("(" + CATEGORIES[key]["query"] + ")")

    custom_query = form.get("custom", "").strip()
    if custom_query:
        labels.append("Custom")
        parts.append("(" + custom_query + ")")

    if not parts:
        raise ValueError("Kam se kam ek category ya custom query select karo.")

    query = " OR ".join(parts)
    date_mode = form.get("date_mode", "all")

    if date_mode == "last":
        days = form.get("days", "").strip()
        if not days.isdigit() or int(days) < 1:
            raise ValueError("Last N days me valid number daalo.")
        query = "(" + query + ") newer_than:" + str(int(days)) + "d"

    elif date_mode == "range":
        after_date = form.get("after", "").strip().replace("-", "/")
        before_date = form.get("before", "").strip().replace("-", "/")
        if not after_date or not before_date:
            raise ValueError("From aur To date dono daalo.")
        query = "(" + query + ") after:" + after_date + " before:" + before_date

    return query, labels


def fetch_thread_ids(service, query):
    ids = []
    page_token = None

    while True:
        kwargs = {"userId": "me", "q": query, "maxResults": 500}
        if page_token:
            kwargs["pageToken"] = page_token

        result = service.users().threads().list(**kwargs).execute()
        ids.extend([thread["id"] for thread in result.get("threads", [])])

        page_token = result.get("nextPageToken")
        if not page_token:
            return ids


def update_job(job_id, **updates):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(updates)


def get_job(job_id):
    with JOBS_LOCK:
        return dict(JOBS.get(job_id, {}))


def seconds_to_text(seconds):
    seconds = int(max(0, seconds or 0))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}h {minutes}m {sec}s"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def trash_threads_with_progress(service, ids, job_id):
    """Move Gmail threads to Trash with live progress + safer retry mode.

    Batch size is 10 for maximum safety.
    Failed requests are retried up to 5 times before being counted as failed.
    """
    total = len(ids)
    batch_size = 10
    max_retries = 5

    update_job(
        job_id,
        total=total,
        status="running",
        message=f"Deleting started... Batch size: {batch_size}, retries: {max_retries}",
    )

    if total == 0:
        update_job(
            job_id,
            status="done",
            percent=100,
            message="No matching emails found.",
            finished_at=time.time(),
        )
        return

    def update_progress_message(extra_message=""):
        job = get_job(job_id)
        done = int(job.get("done", 0))
        failed = int(job.get("failed", 0))
        processed = done + failed
        elapsed = max(0.1, time.time() - float(job.get("started_at", time.time())))
        speed = round(processed / elapsed, 2) if processed else 0
        remaining = max(0, total - processed)
        eta_seconds = int(remaining / speed) if speed > 0 else 0
        percent = round((processed / total) * 100, 1) if total else 100
        filled = min(20, int(percent / 5))

        message = (
            f"[{'█' * filled}{'░' * (20 - filled)}] "
            f"{percent}% | {processed}/{total} | Speed: {speed}/sec | "
            f"ETA: {seconds_to_text(eta_seconds)} | Failed: {failed}"
        )
        if extra_message:
            message += f" | {extra_message}"

        update_job(
            job_id,
            processed=processed,
            percent=percent,
            speed=speed,
            eta=eta_seconds,
            eta_text=seconds_to_text(eta_seconds),
            message=message,
        )

    def trash_chunk(chunk, attempt):
        successful_ids = []
        failed_ids = []

        def callback(request_id, response, exception):
            if exception is None:
                successful_ids.append(request_id)
            else:
                failed_ids.append(request_id)

        batch = BatchHttpRequest(
            callback=callback,
            batch_uri="https://gmail.googleapis.com/batch/gmail/v1",
        )

        for thread_id in chunk:
            batch.add(
                service.users().threads().trash(userId="me", id=thread_id),
                request_id=thread_id,
            )

        try:
            batch.execute()
        except Exception:
            # If the whole batch fails, retry the full chunk.
            failed_ids = list(chunk)
            successful_ids = []

        return successful_ids, failed_ids

    for index in range(0, total, batch_size):
        original_chunk = ids[index:index + batch_size]
        pending = list(original_chunk)

        for attempt in range(1, max_retries + 1):
            if not pending:
                break

            update_progress_message(
                f"Batch {index // batch_size + 1}, attempt {attempt}/{max_retries}"
            )

            successful_ids, failed_ids = trash_chunk(pending, attempt)

            if successful_ids:
                job = get_job(job_id)
                update_job(job_id, done=int(job.get("done", 0)) + len(successful_ids))

            pending = failed_ids

            if pending and attempt < max_retries:
                # Small pause helps Gmail API settle before retry.
                time.sleep(0.8)

        if pending:
            job = get_job(job_id)
            update_job(job_id, failed=int(job.get("failed", 0)) + len(pending))

        update_progress_message()
        time.sleep(0.2)

    job = get_job(job_id)
    done = int(job.get("done", 0))
    failed = int(job.get("failed", 0))
    update_job(
        job_id,
        status="done",
        percent=100,
        eta=0,
        eta_text="0s",
        message=f"Done! {done} threads Gmail Trash me move ho gaye. Failed: {failed}",
        finished_at=time.time(),
    )

def run_trash_job(job_id, query, credentials_info):
    try:
        update_job(job_id, status="scanning", message="Searching matching Gmail threads...")
        service = gmail_service_from_info(credentials_info)
        ids = fetch_thread_ids(service, query)
        update_job(job_id, total=len(ids), message=f"Found {len(ids)} threads. Starting delete...")
        trash_threads_with_progress(service, ids, job_id)
    except Exception as exc:
        update_job(
            job_id,
            status="error",
            message=str(exc),
            finished_at=time.time(),
        )


@app.route("/")
def home():
    if "credentials" in session:
        return redirect(url_for("dashboard"))

    return render_page(
        """
        <div class="box">
          <h2>Connect Gmail</h2>
          <p>Google Cloud me Authorized redirect URI ye add karo:</p>
          <code>{{ callback }}</code>
          <br>
          <a class="btn" href="{{ url_for('login') }}">Login with Google</a>
        </div>
        """,
        callback=callback_url(),
    )


@app.route("/login")
def login():
    flow = Flow.from_client_config(
        client_config(),
        scopes=SCOPES,
        redirect_uri=callback_url(),
    )

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    session["state"] = state
    return redirect(auth_url)


@app.route("/callback")
def callback():
    try:
        flow = Flow.from_client_config(
            client_config(),
            scopes=SCOPES,
            state=session.get("state"),
            redirect_uri=callback_url(),
        )

        auth_response = request.url
        if auth_response.startswith("http://") and "onrender.com" in auth_response:
            auth_response = auth_response.replace("http://", "https://", 1)

        flow.fetch_token(authorization_response=auth_response)
        credentials = flow.credentials

        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        email = service.users().getProfile(userId="me").execute().get("emailAddress", "").lower()

        allow_list = allowed_emails()
        if allow_list and email not in allow_list:
            session.clear()
            return render_page(
                """
                <div class="box">
                  <h2>Access denied</h2>
                  <p>This email is not allowed to use this app.</p>
                  <a class="btn btn2" href="{{ url_for('home') }}">Back</a>
                </div>
                """,
                msg=email + " ALLOWED_EMAILS me nahi hai.",
            )

        session["credentials"] = credentials_to_dict(credentials)
        session["email"] = email
        return redirect(url_for("dashboard"))

    except Exception as exc:
        return render_page(
            """
            <div class="box">
              <h2>OAuth Error</h2>
              <p>Google login complete nahi hua.</p>
              <code>{{ error }}</code>
              <br>
              <a class="btn btn2" href="{{ url_for('home') }}">Try again</a>
            </div>
            """,
            error=str(exc),
            msg="Login failed",
        )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_page(
        """
        <form class="box" method="post" action="{{ url_for('preview') }}">
          <h2>1) Select categories</h2>
          <div class="grid">
            {% for key, category in categories.items() %}
              <label class="opt">
                <input type="checkbox" name="category" value="{{ key }}">
                {{ category.label }}
              </label>
            {% endfor %}
          </div>

          <h2>2) Custom query optional</h2>
          <textarea name="custom" rows="3" placeholder='Example: from:amazon OR subject:"offer"'></textarea>

          <h2>3) Date filter</h2>
          <div class="grid">
            <label class="opt"><input type="radio" name="date_mode" value="all" checked> No filter</label>
            <label class="opt"><input type="radio" name="date_mode" value="last"> Last N days</label>
            <label class="opt"><input type="radio" name="date_mode" value="range"> Date range</label>
          </div>

          <div class="row">
            <label>Last N days
              <input type="number" name="days" min="1" placeholder="30">
            </label>
            <div></div>
          </div>

          <div class="row">
            <label>From
              <input type="date" name="after">
            </label>
            <label>To
              <input type="date" name="before">
            </label>
          </div>

          <br>
          <button class="btn" type="submit">Preview</button>
        </form>
        """,
        categories=CATEGORIES,
    )


@app.route("/preview", methods=["POST"])
@login_required
def preview():
    try:
        query, labels = make_query(request.form)
        ids = fetch_thread_ids(gmail_service(), query)
        session["last_query"] = query

        return render_page(
            """
            <div class="box">
              <h2>Preview</h2>
              <p>Matched Gmail threads: <b>{{ count }}</b></p>
              <p>Selected: {{ labels | join(', ') }}</p>
              <code>{{ query }}</code>
              <br>

              {% if count > 0 %}
                <form method="post" action="{{ url_for('trash') }}">
                  <input type="hidden" name="query" value="{{ query }}">
                  <button class="btn danger" type="submit">Move {{ count }} threads to Trash</button>
                  <a class="btn btn2" href="{{ url_for('dashboard') }}">Cancel</a>
                </form>
              {% else %}
                <a class="btn btn2" href="{{ url_for('dashboard') }}">Back</a>
              {% endif %}
            </div>
            """,
            count=len(ids),
            labels=labels,
            query=query,
            msg="Preview complete",
        )

    except Exception as exc:
        return render_page(
            """
            <div class="box">
              <h2>Preview failed</h2>
              <code>{{ error }}</code>
              <br>
              <a class="btn btn2" href="{{ url_for('dashboard') }}">Back</a>
            </div>
            """,
            error=str(exc),
            msg="Error",
        )


@app.route("/trash", methods=["POST"])
@login_required
def trash():
    query = request.form.get("query", "")

    if not query or query != session.get("last_query"):
        return redirect(url_for("dashboard"))

    job_id = uuid.uuid4().hex
    credentials_info = dict(session.get("credentials", {}))

    with JOBS_LOCK:
        JOBS[job_id] = {
            "status": "starting",
            "query": query,
            "total": 0,
            "done": 0,
            "failed": 0,
            "processed": 0,
            "percent": 0,
            "speed": 0,
            "eta": 0,
            "eta_text": "--",
            "message": "Starting...",
            "started_at": time.time(),
        }

    worker = threading.Thread(
        target=run_trash_job,
        args=(job_id, query, credentials_info),
        daemon=True,
    )
    worker.start()

    return render_page(
        """
        <div class="box">
          <h2>Deleting in progress</h2>
          <p>Is page ko open rehne do. Progress live update hoti rahegi.</p>

          <div class="progress-shell">
            <div id="bar" class="progress-fill"></div>
            <div id="percent" class="progress-label">0%</div>
          </div>

          <div class="stats">
            <div class="stat"><span>Done</span><b id="done">0</b></div>
            <div class="stat"><span>Total</span><b id="total">0</b></div>
            <div class="stat"><span>Speed</span><b id="speed">0/sec</b></div>
            <div class="stat"><span>ETA</span><b id="eta">--</b></div>
            <div class="stat"><span>Failed</span><b id="failed">0</b></div>
          </div>

          <div id="terminal" class="terminal">Starting...</div>

          <div id="finish" style="display:none;margin-top:16px;">
            <a class="btn ok" href="{{ url_for('dashboard') }}">Clean more</a>
          </div>
        </div>

        <script>
          const progressUrl = "{{ url_for('progress', job_id=job_id) }}";

          async function poll() {
            try {
              const response = await fetch(progressUrl, {cache: "no-store"});
              const data = await response.json();
              const percent = Number(data.percent || 0);

              document.getElementById("bar").style.width = percent + "%";
              document.getElementById("percent").textContent = percent.toFixed(1) + "%";
              document.getElementById("done").textContent = data.done || 0;
              document.getElementById("total").textContent = data.total || 0;
              document.getElementById("failed").textContent = data.failed || 0;
              document.getElementById("speed").textContent = (data.speed || 0) + "/sec";
              document.getElementById("eta").textContent = data.eta_text || "--";
              document.getElementById("terminal").textContent = data.message || "Working...";

              if (data.status === "done" || data.status === "error") {
                document.getElementById("finish").style.display = "block";
                return;
              }
            } catch (error) {
              document.getElementById("terminal").textContent = "Progress read error: " + error;
            }

            setTimeout(poll, 1000);
          }

          poll();
        </script>
        """,
        job_id=job_id,
        msg="Live progress started",
    )


@app.route("/progress/<job_id>")
@login_required
def progress(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"status": "error", "message": "Job not found", "percent": 0})
    return jsonify(job)


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
