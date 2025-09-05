# Expense Tracker (multi-household) — Deploy Guide

1. Create GitHub repo and push project.
2. On Render: New → Web Service → Connect repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add Environment Variables:
   - `FLASK_SECRET_KEY` (random strong string)
   - `GOOGLE_CLIENT_ID` (for Google OAuth)
   - `GOOGLE_CLIENT_SECRET`
6. Add Persistent Disk and mount it to `/opt/render/project/src/data` (so SQLite persists).
7. Deploy.
