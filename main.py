from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from typing import List, Optional
import bcrypt
import openai
import httpx
import logging

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "loginpage")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_BASE = os.getenv("OPENROUTER_API_BASE", "https://api.openrouter.ai/v1")

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]  # Lazy-initialized DB client/collections (created on startup)
client = None
db = None
users_coll = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_local_response(prompt: str) -> str:
    """Generate a simple helpful fallback response when external model is unreachable.
    This is a rule-based lightweight responder to provide immediate answers.
    """
    text = prompt.lower()
    # common education/score guidance
    if any(k in text for k in ("score", "how much", "marks", "pass", "pass ca", "ca final")):
        return (
            "General study guidance:\n"
            "1) Focus on high-weight chapters and past papers.\n"
            "2) Aim for safe passing marks (e.g., 50-60%) in tough papers and higher in strengths.\n"
            "3) Break topics into weekly goals and revise regularly.\n"
            "If you share the subject and total marks, I can suggest a specific target."
        )
    if any(k in text for k in ("what is", "explain", "define", "meaning")):
        return "Here is a concise explanation: (I couldn't reach the AI service) — please refine the question for more detail."
    if any(k in text for k in ("how to", "how do i", "steps", "procedure")):
        return "Try these steps: 1) Clarify goal. 2) Break into subtasks. 3) Practice with examples. 4) Review and iterate."
    # fallback generic reply
    return "I couldn't reach the external AI service; here's a helpful template answer: consider clarifying your question, specifying context, and listing constraints."


def extract_text_from_model_response(jr: dict) -> Optional[str]:
    """Attempt to extract a text reply from various model response shapes.
    Returns the first non-empty string found or None.
    """
    if not jr or not isinstance(jr, dict):
        return None
    # try OpenAI Chat-like structure
    try:
        choices = jr.get("choices")
        if isinstance(choices, list) and len(choices) > 0:
            first = choices[0]
            # ChatCompletion message
            msg = None
            if isinstance(first, dict):
                msg = first.get("message") or first.get("delta")
                if isinstance(msg, dict):
                    text = msg.get("content") or msg.get("text")
                    if text:
                        return text
                # fallback to text field
                text = first.get("text")
                if text:
                    return text
    except Exception:
        pass
    # try common alternative fields
    try:
        out = jr.get("output") or {}
        if isinstance(out, dict):
            c = out.get("content") or out.get("text")
            if c:
                return c
        # some routers return top-level 'output_text' or 'response' or 'result'
        for key in ("output_text", "response", "result", "text"):
            v = jr.get(key)
            if isinstance(v, str) and v:
                return v
        # result.content
        res = jr.get("result") or {}
        if isinstance(res, dict):
            v = res.get("content") or res.get("text")
            if v:
                return v
    except Exception:
        pass
    return None


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str | None = None


class AIRequest(BaseModel):
    prompt: str


app = FastAPI()

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    # check mongo connection and report model name
    mongo_ok = False
    try:
        # ping the server
        await client.admin.command("ping")
        mongo_ok = True
    except Exception:
        mongo_ok = False
    return {"status": "ok", "mongoDb": mongo_ok, "model": os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")}


@app.on_event("startup")
async def startup_event():
    global client, db, users_coll
    try:
        client = AsyncIOMotorClient(MONGO_URI)
        db = client[DB_NAME]
        users_coll = db.get_collection("users")
        # try a ping to warm the connection
        try:
            await client.admin.command("ping")
            logger.info("MongoDB ping successful on startup")
        except Exception:
            logger.info("MongoDB ping failed on startup (connection may be unavailable)")
    except Exception:
        logger.exception("Failed to initialize MongoDB client on startup")


@app.on_event("shutdown")
async def shutdown_event():
    global client
    try:
        if client is not None:
            client.close()
            logger.info("MongoDB client closed on shutdown")
    except Exception:
        logger.exception("Error closing MongoDB client on shutdown")


@app.get("/api/openai_status")
async def openai_status():
    """Returns whether an OpenAI API key is configured (does NOT return the key)."""
    configured_openai = bool(OPENAI_API_KEY)
    configured_openrouter = bool(OPENROUTER_API_KEY)
    if configured_openai:
        active = "openai"
    elif configured_openrouter:
        active = "openrouter"
    else:
        active = "mock"
    return {
        "openai_configured": configured_openai,
        "openrouter_configured": configured_openrouter,
        "active_provider": active,
        "model": os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
    }


@app.post("/api/register")
async def register(payload: RegisterRequest):
    existing = await users_coll.find_one({"username": payload.username})
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    pw_hash = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode()
    user_doc = {"username": payload.username, "passwordHash": pw_hash}
    if payload.email:
        user_doc["email"] = payload.email
    res = await users_coll.insert_one(user_doc)
    return {"success": True, "id": str(res.inserted_id)}


@app.post("/api/login")
async def login(payload: LoginRequest):
    user = await users_coll.find_one({"username": payload.username})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    stored_hash = user.get("passwordHash", "")
    if bcrypt.checkpw(payload.password.encode(), stored_hash.encode()):
        return {"success": True, "user": {"username": user["username"], "email": user.get("email")}}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/api/data")
async def post_data(payload: dict):
    """Generic endpoint: stores any JSON payload into `data` collection and returns it."""
    res = await db.get_collection("data").insert_one(payload)
    return {"success": True, "id": str(res.inserted_id), "data": payload}


# Compatibility endpoints expected by the React frontend
class AskRequest(BaseModel):
    userInput: str


class BatchAskRequest(BaseModel):
    userInputs: List[str]


@app.post("/api/ask")
async def ask(payload: AskRequest):
    """Accepts { userInput } and returns { response } so frontend works unchanged."""
    prompt = payload.userInput
    try:
        # Prefer OpenRouter if configured (use async HTTP client)
        if OPENROUTER_API_KEY:
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
            model_name = os.getenv("OPENROUTER_MODEL", "gpt-4o-mini")
            url = f"{OPENROUTER_API_BASE}/chat/completions"
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    url,
                    json={"model": model_name, "messages": [{"role": "user", "content": prompt}]},
                    headers=headers,
                    timeout=30.0,
                )
            r.raise_for_status()
            jr = r.json()
            # try to extract text from various response shapes
            text = extract_text_from_model_response(jr)
            if not text:
                logger.info("No text found in model JSON response; using local fallback")
                return {"response": generate_local_response(prompt)}
            return {"response": text}

        # Fallback to OpenAI SDK if OpenRouter not configured
        if OPENAI_API_KEY:
            resp = openai.ChatCompletion.create(
                model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
            )
            text = resp.choices[0].message.content
            return {"response": text}

        # No key configured: return mock response
        logger.info("No API key configured; returning mock response for /api/ask")
        return {"response": "(mock) OpenRouter/OpenAI API key not configured — this is a placeholder response."}
    except httpx.HTTPStatusError as e:
        logger.exception("HTTP error calling model endpoint: %s", str(e))
        raise HTTPException(status_code=502, detail="Model API returned an error")
    except httpx.ConnectError as e:
        # Network/DNS error calling remote model - return a useful local response instead of 500
        logger.exception("Network error calling model endpoint: %s", str(e))
        return {"response": generate_local_response(prompt)}
    except Exception as e:
        logger.exception("Error in /api/ask")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ask/batch")
async def ask_batch(payload: BatchAskRequest):
    """Accepts { userInputs: [str] } and returns { responses: [str] }"""
    outputs: list[str] = []
    # If OpenAI key present, use it. Else if OpenRouter key present, use it. Otherwise return mock responses.
    # Prefer OpenRouter in batch (async requests)
    if OPENROUTER_API_KEY:
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
        model_name = os.getenv("OPENROUTER_MODEL", "gpt-4o-mini")
        url = f"{OPENROUTER_API_BASE}/chat/completions"
        async with httpx.AsyncClient() as client:
            for prompt in payload.userInputs:
                try:
                    r = await client.post(
                        url,
                        json={"model": model_name, "messages": [{"role": "user", "content": prompt}]},
                        headers=headers,
                        timeout=30.0,
                    )
                    r.raise_for_status()
                    jr = r.json()
                    text = extract_text_from_model_response(jr)
                    if not text:
                        logger.info("No text found in model JSON response for a batch prompt; using local fallback")
                        outputs.append(generate_local_response(prompt))
                    else:
                        outputs.append(text)
                except httpx.ConnectError:
                    logger.exception("Network error in /api/ask/batch for prompt: %s", prompt)
                    outputs.append(generate_local_response(prompt))
                except Exception as e:
                    logger.exception("Error in /api/ask/batch for prompt: %s", prompt)
                    outputs.append(f"Error: {str(e)}")
        return {"responses": outputs}

    # Fallback to OpenAI SDK for batch if available
    if OPENAI_API_KEY:
        for prompt in payload.userInputs:
            try:
                resp = openai.ChatCompletion.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=250,
                )
                text = resp.choices[0].message.content
                outputs.append(text)
            except Exception as e:
                logger.exception("Error in /api/ask/batch for prompt: %s", prompt)
                outputs.append(f"Error: {str(e)}")
        return {"responses": outputs}

    logger.info("No API key configured; returning mock responses for /api/ask/batch")
    return {"responses": ["(mock) OpenRouter/OpenAI API key not configured — placeholder response." for _ in payload.userInputs]}


if __name__ == "__main__":
    import uvicorn

    # Run without the auto-reloader to avoid repeated restarts during development here.
    # If you want live reload locally, run `uvicorn main:app --reload` manually.
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)


@app.post("/api/ai")
async def ai_endpoint(payload: AIRequest):
    """Simple helper endpoint that forwards `prompt` to OpenAI ChatCompletion.
    Requires `OPENAI_API_KEY` set in the environment or `backend/.env`.
    """
    # Prefer OpenRouter if available
    if OPENROUTER_API_KEY:
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
        model_name = os.getenv("OPENROUTER_MODEL", "gpt-4o-mini")
        url = f"{OPENROUTER_API_BASE}/chat/completions"
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    url,
                    json={"model": model_name, "messages": [{"role": "user", "content": payload.prompt}]},
                    headers=headers,
                    timeout=30.0,
                )
            r.raise_for_status()
            jr = r.json()
            text = extract_text_from_model_response(jr) or generate_local_response(payload.prompt)
            return {"success": True, "response": text}
        except httpx.ConnectError as e:
            logger.exception("Network error calling OpenRouter in /api/ai: %s", str(e))
            return {"success": True, "response": generate_local_response(payload.prompt)}
        except Exception as e:
            logger.exception("Error calling OpenRouter in /api/ai: %s", str(e))
            raise HTTPException(status_code=502, detail="Model API error")

    # Fallback to OpenAI if configured
    if OPENAI_API_KEY:
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": payload.prompt}],
                max_tokens=250,
            )
            # extract assistant reply
            text = resp.choices[0].message.content
            return {"success": True, "response": text}
        except Exception as e:
            logger.exception("Error calling OpenAI in /api/ai: %s", str(e))
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=400, detail="No model API key configured (set OPENROUTER_API_KEY or OPENAI_API_KEY)")
