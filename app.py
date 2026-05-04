"""
Gmail Email Cleaner - Advanced Version
=======================================
Custom categories + date range support!

Setup:
  1. pip install google-auth google-auth-oauthlib google-api-python-client
  2. Place credentials.json in same folder
  3. Run: python gmail_cleaner.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📂 CATEGORIES (jo delete kar sakte ho):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1  →  Promotions
  2  →  Newsletters
  3  →  Job Emails
  4  →  Social Notifications
  5  →  Orders & Receipts
  6  →  Spam
  7  →  Custom keyword (apna search daalo)
  A  →  Saari categories ek saath

  Multiple select: 1,3 ya 2,4,6 (comma se alag karo)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 DATE OPTIONS (3 tarike):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Option 1 → Last N Days (kitne din pehle tak)
    Example:  7   = last 1 hafta
              14  = last 2 hafte
              30  = last 1 mahina
              90  = last 3 mahine
              365 = last 1 saal

  Option 2 → Custom Date Range (from - to)
    Format:   YYYY/MM/DD
    Example:  From: 2026/01/01
              To:   2026/04/30
    Matlab:   January se April tak ke emails delete honge

  Option 3 → Koi filter nahi
    Matlab:   Gmail ki puri history mein se delete hoga

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import BatchHttpRequest

SCOPES = ["https://mail.google.com/"]

# ── Predefined Categories ──────────────────────────────────────────────────────
CATEGORIES = {
    "1": {
        "label": "📢 Promotions",
        "query": "category:promotions OR label:promotions",
    },
    "2": {
        "label": "📰 Newsletters",
        "query": (
            "unsubscribe OR from:newsletter OR from:noreply OR from:no-reply "
            "OR subject:newsletter OR subject:digest OR subject:weekly OR subject:\"your briefing\""
        ),
    },
    "3": {
        "label": "💼 Job Emails",
        "query": (
            "from:indeed.com OR from:linkedin.com OR from:shine.com "
            "OR from:internshala.com OR from:naukri.com OR from:jobsora.com "
            "OR from:jobs2web.com OR subject:\"job alert\" OR subject:\"new jobs\" "
            "OR subject:\"apply to jobs\" OR subject:\"vacancy\" "
            "OR subject:\"hiring\" OR subject:\"openings\""
        ),
    },
    "4": {
        "label": "🔔 Social Notifications",
        "query": (
            "category:social OR from:notifications OR "
            "from:noreply@linkedin.com OR from:twitter OR from:facebook"
        ),
    },
    "5": {
        "label": "🛒 Orders & Receipts",
        "query": (
            "subject:order OR subject:receipt OR subject:invoice "
            "OR subject:payment OR subject:\"your purchase\""
        ),
    },
    "6": {
        "label": "📦 Spam",
        "query": "in:spam",
    },
}


# ── Auth ───────────────────────────────────────────────────────────────────────
def authenticate():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES,
                redirect_uri="urn:ietf:wg:oauth:2.0:oob"
            )
            auth_url, _ = flow.authorization_url(prompt="consent")
            print("\n" + "=" * 55)
            print("  Yeh URL browser mein kholo:")
            print("=" * 55)
            print(auth_url)
            print("=" * 55)
            code = input("  Code paste karo: ").strip()
            flow.fetch_token(code=code)
            creds = flow.credentials
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return creds


# ── Date Input ─────────────────────────────────────────────────────────────────
def get_date_range():
    # DATE PATTERNS REMINDER:
    # Option 1: newer_than:Nd   (N = number of days)
    #   e.g.  newer_than:7d   = last 7 days
    #   e.g.  newer_than:30d  = last 30 days
    #
    # Option 2: after:YYYY/MM/DD before:YYYY/MM/DD
    #   e.g.  after:2026/01/01 before:2026/04/30
    #
    # Option 3: no filter = saari history

    print("\n📅 Date range select karo:")
    print("  1. Last N days  (e.g. 7, 14, 30, 90, 365 din)")
    print("  2. Custom range (from date → to date)")
    print("  3. Koi filter nahi (puri Gmail history)")

    choice = input("\nChoice (1/2/3): ").strip()

    if choice == "1":
        days = input("  Kitne din? (e.g. 7): ").strip()
        return f"newer_than:{days}d"

    elif choice == "2":
        print("  Format: YYYY/MM/DD  (e.g. 2026/04/01)")
        from_date = input("  From date: ").strip()
        to_date   = input("  To date:   ").strip()
        try:
            datetime.strptime(from_date, "%Y/%m/%d")
            datetime.strptime(to_date,   "%Y/%m/%d")
            return f"after:{from_date} before:{to_date}"
        except ValueError:
            print("  ⚠️ Galat format! Koi filter apply nahi hoga.")
            return ""
    else:
        return ""  # No filter


# ── Category Selection ─────────────────────────────────────────────────────────
def select_categories():
    print("\n📂 Categories select karo:")
    print("-" * 45)
    for key, cat in CATEGORIES.items():
        print(f"  {key}. {cat['label']}")
    print("  7. 🔍 Custom keyword (apna search daalo)")
    print("  A. ✅ Saari categories (1-6)")
    print("-" * 45)
    print("  💡 Tip: Multiple ke liye comma use karo")
    print("         e.g.  1,3  ya  2,4,6")
    print("-" * 45)

    choice = input("Choice: ").strip().upper()

    selected = []

    if choice == "A":
        selected = list(CATEGORIES.values())
    else:
        keys = [k.strip() for k in choice.split(",")]
        for k in keys:
            if k in CATEGORIES:
                selected.append(CATEGORIES[k])
            elif k == "7":
                keyword = input("  Custom keyword daalo: ").strip()
                if keyword:
                    selected.append({
                        "label": f"🔍 Custom: '{keyword}'",
                        "query": keyword
                    })

    return selected


# ── Core Functions ─────────────────────────────────────────────────────────────
def fetch_thread_ids(service, query):
    ids = []
    page_token = None
    while True:
        kwargs = {"userId": "me", "q": query, "maxResults": 500}
        if page_token:
            kwargs["pageToken"] = page_token
        result = service.users().threads().list(**kwargs).execute()
        threads = result.get("threads", [])
        ids.extend(t["id"] for t in threads)
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return ids


def format_eta(seconds):
    seconds = int(max(0, seconds))
    mins, sec = divmod(seconds, 60)
    hrs, mins = divmod(mins, 60)

    if hrs:
        return f"{hrs}h {mins}m {sec}s"
    if mins:
        return f"{mins}m {sec}s"
    return f"{sec}s"


def progress_bar(done, total, width=26):
    if total <= 0:
        return "[" + "-" * width + "] 0%"

    percent = done / total
    filled = int(width * percent)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {percent * 100:5.1f}%"


def make_run_id(thread_ids):
    raw = "|".join(thread_ids[:20] + thread_ids[-20:] + [str(len(thread_ids))])
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def save_resume_state(pause_file, run_id, remaining_ids, original_total, done_count):
    pause_file.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "original_total": original_total,
                "done_count": done_count,
                "remaining_ids": remaining_ids,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def trash_threads(service, thread_ids):
    """
    Termux-stable Gmail trash:
    - Correct Gmail BatchHttpRequest endpoint
    - No parallel threads
    - Visual progress bar
    - ETA
    - Pause/resume
    """

    if not thread_ids:
        print("  ✅ Kuch trash karne ke liye nahi mila.")
        return 0

    original_total = len(thread_ids)
    run_id = make_run_id(thread_ids)
    pause_file = Path("gmail_cleaner_resume.json")

    # Termux-safe batch size
    batch_size = 20

    ids_to_process = list(thread_ids)
    done_before = 0

    if pause_file.exists():
        try:
            data = json.loads(pause_file.read_text(encoding="utf-8"))

            if data.get("run_id") == run_id and data.get("remaining_ids"):
                saved_done = int(data.get("done_count", 0))
                saved_total = int(data.get("original_total", original_total))

                choice = input(
                    f"  ⏸️ Same run resume file mila: {saved_done}/{saved_total} done. Resume? (yes/no): "
                ).strip().lower()

                if choice in ("yes", "y", "ha", "haan"):
                    ids_to_process = data["remaining_ids"]
                    done_before = saved_done
                    original_total = saved_total
                    print(f"  ▶️ Resuming from {done_before}/{original_total} ...")
                else:
                    pause_file.unlink(missing_ok=True)
            else:
                print("  ℹ️ Old/different resume file ignore kar di.")
                pause_file.unlink(missing_ok=True)

        except Exception:
            pause_file.unlink(missing_ok=True)

    total_remaining = len(ids_to_process)
    remaining_set = set(ids_to_process)

    success_count = 0
    failed_count = 0
    start_time = time.time()

    print()
    print("  🚀 Stable Fast Mode ON — Gmail Batch API")
    print(f"  📦 Original total: {original_total}")
    print(f"  🧹 Remaining now: {total_remaining}")
    print(f"  ⚡ Batch size: {batch_size}")
    print("  🔒 Parallel OFF for Termux stability")
    print("  ✅ Correct batch endpoint: https://gmail.googleapis.com/batch/gmail/v1")
    print("  ⏸️ Pause karna ho to Ctrl + C dabao. Dobara run karoge to resume hoga.")
    print()

    def print_progress():
        done_total = done_before + success_count
        elapsed = time.time() - start_time
        speed = success_count / elapsed if elapsed > 0 else 0
        remaining = max(0, original_total - done_total)
        eta = remaining / speed if speed > 0 else 0

        print(
            f"  {progress_bar(done_total, original_total)} "
            f"| {done_total}/{original_total} "
            f"| Speed: {speed:.1f}/sec "
            f"| ETA: {format_eta(eta)} "
            f"| Failed: {failed_count}",
            flush=True
        )

    try:
        for i in range(0, total_remaining, batch_size):
            chunk = ids_to_process[i:i + batch_size]

            successful_ids = []
            failed_ids = []

            def callback(request_id, response, exception):
                if exception is None:
                    successful_ids.append(request_id)
                else:
                    failed_ids.append(request_id)
                    print(f"  ⚠️ Failed {request_id}: {exception}")

            # Important fix:
            # Old default URL https://www.googleapis.com/batch gives 404.
            batch = BatchHttpRequest(
                callback=callback,
                batch_uri="https://gmail.googleapis.com/batch/gmail/v1"
            )

            for tid in chunk:
                batch.add(
                    service.users().threads().trash(userId="me", id=tid),
                    request_id=tid
                )

            batch.execute()

            success_count += len(successful_ids)
            failed_count += len(failed_ids)

            for sid in successful_ids:
                remaining_set.discard(sid)

            save_resume_state(
                pause_file,
                run_id,
                list(remaining_set),
                original_total,
                done_before + success_count,
            )

            print_progress()
            time.sleep(0.5)

        if remaining_set:
            save_resume_state(
                pause_file,
                run_id,
                list(remaining_set),
                original_total,
                done_before + success_count,
            )
            print()
            print(f"  ⚠️ {len(remaining_set)} emails remaining hain. Dobara run karke retry/resume kar sakte ho.")
        else:
            pause_file.unlink(missing_ok=True)
            print()
            print(f"  ✅ Done! {success_count} emails Gmail Trash me move ho gaye.")

        return success_count

    except KeyboardInterrupt:
        save_resume_state(
            pause_file,
            run_id,
            list(remaining_set),
            original_total,
            done_before + success_count,
        )
        print()
        print(f"  ⏸️ Paused safely at {done_before + success_count}/{original_total}.")
        print("  ▶️ Resume ke liye same script dobara run karo aur yes likho.")
        return success_count

    except Exception as e:
        save_resume_state(
            pause_file,
            run_id,
            list(remaining_set),
            original_total,
            done_before + success_count,
        )
        print()
        print(f"  ⚠️ Error aaya: {e}")
        print(f"  💾 Progress saved at {done_before + success_count}/{original_total}.")
        print("  ▶️ Dobara run karke resume kar sakte ho.")
        return success_count



# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "=" * 55)
    print("  📬  Gmail Email Cleaner - Advanced")
    print("=" * 55)

    print("\n🔐 Authenticating ...")
    creds = authenticate()
    service = build("gmail", "v1", credentials=creds)
    print("  ✅ Authenticated!\n")

    while True:
        print("\n" + "=" * 55)
        print("  1. Emails delete karo")
        print("  2. Quit")
        print("=" * 55)

        action = input("Choice (1/2): ").strip()

        if action == "2" or action.lower() in ("quit", "exit", "q"):
            print("\nBye! 👋")
            break

        if action != "1":
            print("⚠️  Sirf 1 ya 2 daalo!")
            continue

        # Step 1: Categories
        categories = select_categories()
        if not categories:
            print("⚠️  Koi category select nahi hui!")
            continue

        # Step 2: Date range
        date_filter = get_date_range()

        # Step 3: Confirm
        print("\n" + "-" * 45)
        print("📋 Summary — Yeh delete hoga:")
        for cat in categories:
            print(f"  • {cat['label']}")
        print(f"  📅 Date: {date_filter if date_filter else 'Koi filter nahi (saari history)'}")
        print("-" * 45)

        confirm = input("Confirm? (yes/no): ").strip().lower()
        if confirm not in ("yes", "y", "ha", "haan"):
            print("❌ Cancel!")
            continue

        # Step 4: Delete
        total = 0
        for cat in categories:
            query = f"({cat['query']}) {date_filter}" if date_filter else cat["query"]
            print(f"\n🔍 Searching: {cat['label']} ...")
            ids = fetch_thread_ids(service, query)

            if not ids:
                print("  ✅ Kuch nahi mila!")
                continue

            print(f"  Found {len(ids)} emails. Trashing ...")
            count = trash_threads(service, ids)
            total += count
            print(f"  ✅ {count} emails trashed!")

        print(f"\n🎉 Total {total} emails Trash mein gaye!\n")


if __name__ == "__main__":
    main()
    