<<<<<<< HEAD
# Education Prompt Frontend

This Vite app is a small UI for testing the Flask backend in `../backend`.

## Run the frontend

```bash
npm install
npm run dev
```

By default the app sends requests to the Flask backend through the Vite proxy, so keep the backend running on `http://localhost:5000`.

If your Flask server runs somewhere else, create a `.env` file in this folder and set:

```bash
VITE_API_BASE_URL=http://localhost:5000
```
=======
# Backend (FastAPI)

Simple FastAPI backend for the `loginpage` frontend.

Run (Windows):

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Run (macOS / Linux):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Endpoints:

- `GET /api/health` — health check
- `POST /api/login` — JSON body `{ "username": "...", "password": "..." }` (mock auth: `admin` / `password`)
 - `POST /api/register` — JSON body `{ "username":"...", "password":"...", "email":"..." }` (creates user)
 - `POST /api/login` — JSON body `{ "username": "...", "password": "..." }` (verifies password)
 - `POST /api/data` — any JSON body; stores in `data` collection and returns stored document

Notes:

- CORS allows `http://localhost:5173` (Vite dev server). Adjust in `backend/main.py` if needed.
- Replace mock auth with real database logic for production.
 
Environment

- Create a `.env` file in the `backend` folder with values:

```
MONGO_URI=mongodb://localhost:27017
DB_NAME=loginpage
```

Then run the server as above. Ensure MongoDB is running and reachable at `MONGO_URI`.

OpenAI integration

- To enable the optional OpenAI helper endpoint, add your key to `backend/.env`:

```
OPENAI_API_KEY=your_openai_api_key_here
```

- Endpoint: `POST /api/ai` with JSON `{ "prompt": "..." }` — returns OpenAI reply.

Security note: never commit your real API key to git. Use environment variables or a secrets manager.
>>>>>>> 7f6ba6e (first commit)
"# orionagent" 
"# orionagent" 
