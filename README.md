# Task Assistant

Task Assistant is a full-stack personal task manager with JWT authentication, private task and conversation data, and an AI chat integration point for Google ADK/Gemini.

## Current MVP features

- FastAPI backend with SQLite and SQLAlchemy
- Argon2 password hashing and JWT bearer authentication
- User registration, login, and current-user endpoint
- Authenticated task CRUD with user ownership isolation
- Task priorities, categories, due dates, estimated durations, filtering, and sorting
- Goals with milestones, progress, target dates, and linked tasks
- AI-generated goal breakdown proposals requiring explicit approval
- Conversation and message history endpoints
- React/Vite/Tailwind dashboard with login, registration, task checklist, and chat UI
- Explicit `503` response when Gemini is not configured instead of a fabricated assistant response

## Run on Windows PowerShell

### Backend

```powershell
cd C:\Users\hp\task-assistant\backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and set a strong JWT_SECRET_KEY.
uvicorn app.main:app --reload
```

If PowerShell says port 8000 is already in use, find the terminal where an old
Uvicorn process is running and press `Ctrl+C` there. Then run the command above
once. Do not start multiple backend servers on port 8000.

The API is available at `http://localhost:8000`. OpenAPI documentation is at `http://localhost:8000/docs`.

If the frontend shows “Cannot reach the backend” or registration returns an unexpected
server error, stop the old Uvicorn process and start it again from the `backend`
directory:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
# Stop only the process ID shown by the command above:
Stop-Process -Id <PID>
uvicorn app.main:app --reload
```

### Frontend

```powershell
cd C:\Users\hp\task-assistant\frontend
npm install
npm run dev
```

The dashboard is available at `http://localhost:5173`.

The Vite development server proxies `/api` requests to
`http://127.0.0.1:8000`, which avoids browser CORS errors when Vite chooses
port 5174 instead of 5173. Restart the frontend after changing
`vite.config.js`.

## Environment

Set these values in `backend/.env`:

```text
DATABASE_URL=sqlite:///./task_assistant.db
JWT_SECRET_KEY=replace_with_secure_random_secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-flash-lite-latest
GEMINI_FALLBACK_MODEL=gemini-flash-latest
FRONTEND_URL=http://localhost:5173
```

Never commit `.env` or put `GOOGLE_API_KEY` in the frontend.

## API endpoints

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/tasks`
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `PATCH /api/tasks/{task_id}`
- `DELETE /api/tasks/{task_id}`
- `POST /api/goals`
- `GET /api/goals`
- `GET /api/goals/{goal_id}`
- `PATCH /api/goals/{goal_id}`
- `DELETE /api/goals/{goal_id}`
- `POST /api/goals/{goal_id}/milestones`
- `PATCH /api/goals/{goal_id}/milestones/{milestone_id}`
- `DELETE /api/goals/{goal_id}/milestones/{milestone_id}`
- `POST /api/goals/{goal_id}/breakdown`
- `POST /api/goals/{goal_id}/breakdown/approve`
- `POST /api/chat`
- `GET /api/chat/conversations`
- `GET /api/chat/conversations/{conversation_id}/messages`

Task creation and updates accept:

```json
{
  "title": "Complete my CV",
  "priority": "urgent",
  "due_date": "2030-01-02T10:00:00Z",
  "category": "Career",
  "estimated_minutes": 120
}
```

`priority` must be `low`, `medium`, `high`, or `urgent`. `estimated_minutes` must
be a positive integer. `GET /api/tasks` supports `priority`, `category`,
`completed`, and `sort=created|due_date|priority` query parameters. Tasks may
also include an optional authenticated `goal_id`.

Goals accept `title`, `description`, `start_date`, `target_date`, `status`
(`active`, `completed`, `paused`, or `archived`), and `progress` from 0 to 100.
The breakdown endpoint returns proposed milestones and tasks without saving
them. The approval endpoint persists the proposal and links its tasks to the
goal.
Tasks may additionally include `milestone_id`; the API verifies that the
milestone belongs to the authenticated user and automatically keeps the task's
`goal_id` consistent. Passing `milestone_id: null` removes the milestone link
while retaining the goal link.

## Tests

```powershell
cd C:\Users\hp\task-assistant
$env:PYTHONPATH="backend"
backend\.venv\Scripts\pytest.exe backend\tests -q
```

The test suite uses a temporary SQLite database and does not modify the development database.

## AI integration

When `GOOGLE_API_KEY` is configured, `POST /api/chat` runs a Google ADK single-turn Gemini agent with `list_tasks`, `add_task`, `update_task`, and `delete_task` tools. The tools close over the verified backend user and query by that user ID, so the model cannot choose another owner. If the key is missing or Gemini returns no usable response, the endpoint returns `503` instead of fabricating an answer.
