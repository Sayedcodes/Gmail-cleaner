# 📬 Gmail Cleaner

A web app to bulk delete unwanted Gmail emails — fast, smart, and easy to use. Built with Python, Flask, and Gmail API.

---

## ✨ Features

- **6 Built-in Categories** — Promotions, Newsletters, Job Emails, Social Notifications, Orders & Receipts, Spam
- **Custom Keyword Search** — Delete any emails by your own search query
- **Date Range Filter** — Last N days, custom date range, or entire inbox history
- **Batch Delete** — Uses Gmail Batch API to delete 20 emails at once (super fast)
- **Live Progress Bar** — Real-time updates in browser via Server-Sent Events (SSE)
- **Pause / Resume / Stop** — Full control during deletion process
- **Whitelist Access Control** — Only authorized emails can use the app
- **Google OAuth 2.0** — Each user logs in with their own Gmail account (no shared passwords)
- **Deployed on Render.com** — Free hosting, always online

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Gmail Integration | Google Gmail API v1 |
| Authentication | Google OAuth 2.0 |
| Real-time Progress | Server-Sent Events (SSE) |
| Hosting | Render.com |

---

## 🚀 Deployment (Render.com)

### 1. Clone the repo
```bash
git clone https://github.com/your-username/gmail-cleaner.git
cd gmail-cleaner
```

### 2. Set up Google Cloud
- Enable **Gmail API** in [Google Cloud Console](https://console.cloud.google.com)
- Create **OAuth 2.0 credentials** (Desktop App type)
- Add authorized redirect URI: `https://your-app.onrender.com/callback`

### 3. Deploy on Render.com
- Connect your GitHub repo
- Set **Start Command:** `gunicorn app:app`
- Add these **Environment Variables:**

| Variable | Value |
|---|---|
| `SECRET_KEY` | any random string |
| `FLASK_ENV` | `production` |
| `GOOGLE_CREDENTIALS_JSON` | paste full contents of `credentials.json` |
| `ALLOWED_EMAILS` | `email1@gmail.com,email2@gmail.com` |

---

## 🔒 Access Control

Only emails listed in `ALLOWED_EMAILS` env variable can use the app.

```
# Allow specific users
ALLOWED_EMAILS=sister@gmail.com,friend@gmail.com

# Allow everyone (leave empty)
ALLOWED_EMAILS=
```

To add or remove users — just edit this variable on Render.com dashboard and save. App redeploys automatically.

---

## 💻 Local Development

```bash
pip install -r requirements.txt
python app.py
```

Open browser at `http://localhost:5000`

> Make sure `credentials.json` is in the same folder.

---

## 📋 How It Works

1. User opens the app and logs in with Google
2. Selects email categories to delete
3. Chooses a date range
4. Clicks **Delete** — batch deletion starts instantly
5. Live progress bar shows speed, ETA, and count
6. Pause or stop anytime — resume later

---

## ⚠️ Notes

- Emails are moved to **Trash**, not permanently deleted (recoverable within 30 days)
- Gmail API free quota: **1 billion units/day** — practically unlimited
- Google OAuth testing mode supports up to **100 users**

---

## 📄 MIT License

Private project — all rights reserved.
