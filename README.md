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
"# orionagent" 
