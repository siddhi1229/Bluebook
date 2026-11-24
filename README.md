# BlueBook Tracker

BlueBook Tracker records examination room booklet issue and return quantities. Room invigilator assignments are created separately for every examination, preserving historical records. The backend is the source of truth for reconciliation, statuses, dashboard counts and alerts.

## Requirements

- Python 3.11+
- Node.js 20+
- Optional Gemini API key for generated summaries

## Start locally

1. In `backend`, create/activate a virtual environment and install dependencies with `pip install -r requirements.txt`.
2. Copy `.env.example` to `.env`, set a strong `JWT_SECRET` and initial coordinator credentials, then run `uvicorn app.main:app --reload` from `backend`.
3. In `frontend`, run `npm install`, then `npm run dev`.
4. Open `http://localhost:5173`. The first backend start creates the coordinator account from `ADMIN_EMAIL` and `ADMIN_PASSWORD` (defaults are for local development only).

The API documentation is available at `http://localhost:8000/docs`. SQLite data is stored in `backend/bluebook.db` when run from the backend directory. Set `GEMINI_API_KEY` to enable AI-written explanations; core tracking works without it and provides a fallback message.

## Roles and workflow

- Coordinators create examinations, rooms, invigilators and examination-specific assignments, then review logs and resolve alerts.
- Invigilators see only their own assignments and submit an issue quantity once, followed by one final return quantity submission.
- Return processing calculates `issued - (used + unused)` in the backend. Matched records have no alert; shortages and excess returns create alerts. Resolving an alert never edits counts.

No student records or student counts are stored.
