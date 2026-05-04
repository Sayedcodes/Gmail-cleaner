import json
import os
from functools import wraps

os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from flask import Flask, redirect, render_template_string, request, session, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import BatchHttpRequest
from werkzeug.middleware.proxy_fix import ProxyFix

SCOPES = ["https://mail.google.com/"]

CATEGORIES = {
    "promotions": ("Promotions", "category:promotions OR label:promotions"),
    "newsletters": ("Newsletters", "unsubscribe OR from:newsletter OR from:noreply OR from:no-reply OR subject:newsletter OR subject:digest"),
    "jobs": ("Job Emails", "from:indeed.com OR from:linkedin.com OR from:shine.com OR from:internshala.com OR from:naukri.com OR subject:\"job alert\" OR subject:hiring OR subject:openings"),
    "social": ("Social Notifications", "category:social OR from:notifications OR from:noreply@linkedin.com OR from:twitter OR from:facebook"),
    "orders": ("Orders & Receipts", "subject:order OR subject:receipt OR subject:invoice OR subject:payment OR subject:\"your purchase\""),
    "spam": ("Spam", "in:spam"),
}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

STYLE = """
<style>
body{margin:0;font-family:Arial,Segoe UI,sans-serif;background:#0f1117;color:#f5f5f5;padding:24px} .box{max-width:850px;margin:0 auto 18px;background:#171a23;border:1px solid #2b3242;border-radius:18px;padding:22px;box-shadow:0 18px 45px #0006} h1{margin:0;font-size:34px} h2{margin-top:0} p{color:#b9c0d0;line-height:1.5}.btn{display:inline-block;border:0;border-radius:12px;padding:12px 16px;background:#8b5cf6;color:white;text-decoration:none;font-weight:700;cursor:pointer}.btn2{background:#252b3b}.danger{background:#ef4444}.ok{background:#22c55e;color:#07130b}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}.opt{background:#202637;border:1px solid #343b4e;border-radius:13px;padding:13px;display:flex;gap:10px;align-items:center}input,textarea{width:100%;box-sizing:border-box;margin-top:7px;background:#0c101a;color:white;border:1px solid #343b4e;border-radius:10px;padding:11px}input[type=checkbox],input[type=radio]{width:auto;margin:0}code{white-space:pre-wrap;display:block;background:#0b0f18;border:1px solid #343b4e;border-radius:10px;padding:12px;overflow-wrap:anywhere}.msg{max-width:850px;margin:0 auto 18px;border-radius:14px;padding:14px;background:#121827;border-left:4px solid #8b5cf6}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:700px){.row{grid-template-columns:1fr}body{padding:12px}}
</style>
"""


def render(body, **ctx):
    html = """
    <!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>Gmail Cleaner</title>""" + STYLE + """</head><body>
    {% if msg %}<div class='msg'>{{ msg }}</div>{% endif %}
    <div class='box'><h1>Gmail Cleaner</h1><p>Emails permanently delete nahi honge, sirf Gmail Trash me move honge.</p>
    {% if email %}<p>Logged in: <b>{{ email }}</b> &nbsp; <a class='btn btn2' href='{{ url_for("logout") }}'>Logout</a></p>{% endif %}</div>
    """ + body + """</body></html>"""
    return render_template_string(html, email=session.get("email"), **ctx)


def base_url():
    return (os.environ.get("PUBLIC_BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL") or request.host_url).rstrip("/")


def callback_url():
    return base_url() + "/callback"


def client_config():
    raw = os.environ.get("GOOGLE_CREDENTIALS_JSON", "").strip()
    if raw:
        return json.loads(raw)
    if os.path.exists("credentials.json"):
        with open("credentials.json", "r", encoding="utf-8") as f:
            return json.load(f)
    raise RuntimeError("GOOGLE_CREDENTIALS_JSON missing hai. Render Environment me credentials.json ka full content paste karo.")


def allowed_emails():
    raw = os.environ.get("ALLOWED_EMAILS", "").strip().lower()
    return [x.strip() for x in raw.split(",") if x.strip()] if raw else []


def cred_to_dict(c):
    return {"token": c.token, "refresh_token": c.refresh_token, "token_uri": c.token_uri, "client_id": c.client_id, "client_secret": c.client_secret, "scopes": c.scopes}


def creds():
    info = session.get("credentials")
    if not info:
        raise RuntimeError("Login required")
    c = Credentials.from_authorized_user_info(info, SCOPES)
    if c.expired and c.refresh_token:
        c.refresh(Request())
        session["credentials"] = cred_to_dict(c)
    return c


def service():
    return build("gmail", "v1", credentials=creds(), cache_discovery=False)


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
            labels.append(CATEGORIES[key][0])
            parts.append("(" + CATEGORIES[key][1] + ")")
    custom = form.get("custom", "").strip()
    if custom:
        labels.append("Custom")
        parts.append("(" + custom + ")")
    if not parts:
        raise ValueError("Kam se kam ek category ya custom query select karo.")
    q = " OR ".join(parts)
    mode = form.get("date_mode", "all")
    if mode == "last":
        days = form.get("days", "").strip()
        if not days.isdigit() or int(days) < 1:
            raise ValueError("Last days me valid number daalo.")
        q = "(" + q + ") newer_than:" + str(int(days)) + "d"
    elif mode == "range":
        after = form.get("after", "").strip().replace("-", "/")
        before = form.get("before", "").strip().replace("-", "/")
        if not after or not before:
            raise ValueError("From aur To date dono daalo.")
        q = "(" + q + ") after:" + after + " before:" + before
    return q, labels


def fetch_thread_ids(svc, query):
    ids, token = [], None
    while True:
        args = {"userId": "me", "q": query, "maxResults": 500}
        if token:
            args["pageToken"] = token
        res = svc.users().threads().list(**args).execute()
        ids.extend([t["id"] for t in res.get("threads", [])])
        token = res.get("nextPageToken")
        if not token:
            return ids


def trash_threads(svc, ids):
    success = 0
    failed = 0
    for i in range(0, len(ids), 50):
        chunk = ids[i:i+50]
        def cb(request_id, response, exception):
            nonlocal success, failed
            if exception is None:
                success += 1
            else:
                failed += 1
        batch = BatchHttpRequest(callback=cb, batch_uri="https://gmail.googleapis.com/batch/gmail/v1")
        for tid in chunk:
            batch.add(svc.users().threads().trash(userId="me", id=tid), request_id=tid)
        batch.execute()
    return success, failed


@app.route("/")
def home():
    if "credentials" in session:
        return redirect(url_for("dashboard"))
    return render("""
    <div class='box'><h2>Connect Gmail</h2><p>Google Cloud me Authorized redirect URI ye add karo:</p><code>{{ cb }}</code><br><a class='btn' href='{{ url_for("login") }}'>Login with Google</a></div>
    """, cb=callback_url(), msg=None)


@app.route("/login")
def login():
    flow = Flow.from_client_config(client_config(), scopes=SCOPES, redirect_uri=callback_url())
    auth_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    session["state"] = state
    return redirect(auth_url)


@app.route("/callback")
def callback():
    try:
        flow = Flow.from_client_config(client_config(), scopes=SCOPES, state=session.get("state"), redirect_uri=callback_url())
        auth_response = request.url
        if auth_response.startswith("http://") and "onrender.com" in auth_response:
            auth_response = auth_response.replace("http://", "https://", 1)
        flow.fetch_token(authorization_response=auth_response)
        c = flow.credentials
        svc = build("gmail", "v1", credentials=c, cache_discovery=False)
        email = svc.users().getProfile(userId="me").execute().get("emailAddress", "").lower()
        allow = allowed_emails()
        if allow and email not in allow:
            session.clear()
            return render("<div class='box'><h2>Access denied</h2><p>This email is not allowed.</p><a class='btn btn2' href='/'>Back</a></div>", msg=email + " ALLOWED_EMAILS me nahi hai")
        session["credentials"] = cred_to_dict(c)
        session["email"] = email
        return redirect(url_for("dashboard"))
    except Exception as e:
        return render("<div class='box'><h2>OAuth Error</h2><code>{{ error }}</code><br><a class='btn btn2' href='/'>Try again</a></div>", error=str(e), msg="Login failed")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render("""
    <form class='box' method='post' action='{{ url_for("preview") }}'>
      <h2>1) Select categories</h2><div class='grid'>{% for key, value in cats.items() %}<label class='opt'><input type='checkbox' name='category' value='{{ key }}'> {{ value[0] }}</label>{% endfor %}</div>
      <h2>2) Custom query optional</h2><textarea name='custom' rows='3' placeholder='Example: from:amazon OR subject:"offer"'></textarea>
      <h2>3) Date filter</h2><div class='grid'><label class='opt'><input type='radio' name='date_mode' value='all' checked> No filter</label><label class='opt'><input type='radio' name='date_mode' value='last'> Last N days</label><label class='opt'><input type='radio' name='date_mode' value='range'> Date range</label></div>
      <div class='row'><label>Last N days<input type='number' name='days' min='1' placeholder='30'></label><div></div></div>
      <div class='row'><label>From<input type='date' name='after'></label><label>To<input type='date' name='before'></label></div><br>
      <button class='btn' type='submit'>Preview</button>
    </form>
    """, cats=CATEGORIES, msg=None)


@app.route("/preview", methods=["POST"])
@login_required
def preview():
    try:
        q, labels = make_query(request.form)
        ids = fetch_thread_ids(service(), q)
        session["last_query"] = q
        return render("""
        <div class='box'><h2>Preview</h2><p>Matched Gmail threads: <b>{{ count }}</b></p><p>Selected: {{ labels|join(', ') }}</p><code>{{ q }}</code><br>
        {% if count > 0 %}<form method='post' action='{{ url_for("trash") }}'><input type='hidden' name='query' value='{{ q }}'><button class='btn danger' type='submit'>Move {{ count }} threads to Trash</button> <a class='btn btn2' href='{{ url_for("dashboard") }}'>Cancel</a></form>{% else %}<a class='btn btn2' href='{{ url_for("dashboard") }}'>Back</a>{% endif %}</div>
        """, count=len(ids), labels=labels, q=q, msg="Preview complete")
    except Exception as e:
        return render("<div class='box'><h2>Preview failed</h2><code>{{ error }}</code><br><a class='btn btn2' href='{{ url_for("dashboard") }}'>Back</a></div>", error=str(e), msg="Error")


@app.route("/trash", methods=["POST"])
@login_required
def trash():
    q = request.form.get("query", "")
    if not q or q != session.get("last_query"):
        return redirect(url_for("dashboard"))
    try:
        svc = service()
        ids = fetch_thread_ids(svc, q)
        success, failed = trash_threads(svc, ids)
        return render("<div class='box'><h2>Done</h2><p><b>{{ success }}</b> threads Trash me move ho gaye.</p><p>Failed: <b>{{ failed }}</b></p><a class='btn ok' href='{{ url_for("dashboard") }}'>Clean more</a></div>", success=success, failed=failed, msg="Trash operation complete")
    except Exception as e:
        return render("<div class='box'><h2>Trash failed</h2><code>{{ error }}</code><br><a class='btn btn2' href='{{ url_for("dashboard") }}'>Back</a></div>", error=str(e), msg="Error")


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
