"""Outside-the-home access: requests that arrive through the HTTPS gateway (Caddy on the mini-PC) must sign in
with a personal username + password + authenticator code before the usual PIN screen. LAN use is unchanged."""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import pyotp
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

router = APIRouter(prefix="/api/remote")
D = {}  # db, session_cookie, ttl_days, set_cookie — filled in by server.py

REMOTE_HEADER = "x-smith-remote"
LOCK_AFTER = 5
LOCK_MINUTES = 15
MIN_PASSWORD = 12
ISSUER = "Smith Apartment"

# Paths that never make sense from the internet (device webhooks, demo bypass, OAuth callback).
REMOTE_BLOCKED = ("/api/protect/webhook/", "/api/voice/", "/api/spotify/callback", "/api/auth/demo")
REMOTE_PUBLIC = {"/api", "/api/", "/api/bootstrap", "/api/remote/login", "/api/remote/me"}


def _now():
    return datetime.now(timezone.utc)


def is_remote(request: Request) -> bool:
    """The gateway sets this header on every internet request (overwriting anything sent by the client).
    Anyone adding it on the LAN only makes their own request stricter, so no source check is needed."""
    return REMOTE_HEADER in request.headers


def client_ip(request: Request) -> str:
    if is_remote(request):
        return (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


async def session_doc(request: Request) -> Optional[dict]:
    token = request.cookies.get(D["session_cookie"])
    if not token:
        return None
    doc = await D["db"].sessions.find_one({"token": token})
    if not doc or datetime.fromisoformat(doc["expires_at"]) < _now():
        return None
    return doc


async def gate(request: Request, path: str):
    """Auth decision for remote requests. Returns None to allow, or (status, detail) to reject."""
    if path.startswith(REMOTE_BLOCKED):
        return 404, "Not found"
    if path in REMOTE_PUBLIC:
        return None
    s = await session_doc(request)
    if not s or not s.get("remote"):
        return 401, "Sign in required"
    if path == "/api/auth/pin" or s.get("pin_ok"):
        return None
    return 401, "Not authenticated"


# ---------------------------------------------------------------- sign in

class LoginReq(BaseModel):
    username: str
    password: str
    code: Optional[str] = None


async def _locked(ident: str) -> int:
    a = await D["db"].login_attempts.find_one({"identifier": ident})
    if a and a.get("locked_until") and datetime.fromisoformat(a["locked_until"]) > _now():
        return int((datetime.fromisoformat(a["locked_until"]) - _now()).total_seconds()) + 1
    return 0


async def _fail(ident: str):
    a = await D["db"].login_attempts.find_one({"identifier": ident}) or {}
    fails = int(a.get("fails", 0)) + 1
    upd = {"fails": fails, "updated_at": _now().isoformat()}
    if fails >= LOCK_AFTER:
        upd.update(fails=0, locked_until=(_now() + timedelta(minutes=LOCK_MINUTES)).isoformat())
    await D["db"].login_attempts.update_one({"identifier": ident}, {"$set": upd}, upsert=True)


def _code_ok(user: dict, secret: str, code: str) -> Optional[int]:
    """Valid, not-yet-used 30 s step for this code, else None (blocks replaying a code)."""
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(code) != 6:
        return None
    totp = pyotp.TOTP(secret)
    now = _now()
    for drift in (-1, 0, 1):
        t = now + timedelta(seconds=30 * drift)
        if secrets.compare_digest(totp.at(t), code):
            step = int(t.timestamp()) // 30
            return step if step > int(user.get("last_step", -1)) else None
    return None


@router.post("/login")
async def login(req: LoginReq, request: Request, response: Response):
    if not is_remote(request):
        raise HTTPException(400, "Outside sign-in is only used when connecting from outside the apartment")
    username = req.username.strip().lower()
    ident = f"{client_ip(request)}:{username}"
    wait = await _locked(ident)
    if wait:
        raise HTTPException(429, f"Too many attempts. Try again in {wait // 60 + 1} min.")
    db = D["db"]
    user = await db.remote_users.find_one({"username": username})
    if not user or user.get("disabled") or not verify_password(req.password, user["password_hash"]):
        await _fail(ident)
        raise HTTPException(401, "Wrong username or password")

    if not user.get("totp_confirmed"):
        secret = user.get("totp_secret") or pyotp.random_base32()
        if not user.get("totp_secret"):
            await db.remote_users.update_one({"_id": user["_id"]}, {"$set": {"totp_secret": secret}})
        if not req.code:
            uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=ISSUER)
            return {"step": "enroll", "otpauth_uri": uri, "secret": secret}
    else:
        secret = user["totp_secret"]
        if not req.code:
            return {"step": "code"}

    step = _code_ok(user, secret, req.code)
    if step is None:
        await _fail(ident)
        raise HTTPException(401, "That code didn't work. Use the newest 6-digit code from your authenticator app.")

    await db.login_attempts.delete_one({"identifier": ident})
    await db.remote_users.update_one({"_id": user["_id"]}, {"$set": {
        "totp_confirmed": True, "last_step": step, "last_login_at": _now().isoformat(), "last_login_ip": client_ip(request)}})
    token = secrets.token_urlsafe(32)
    await db.sessions.insert_one({"token": token, "remote": True, "user_id": str(user["_id"]), "username": username,
                                  "pin_ok": False, "created_at": _now().isoformat(),
                                  "expires_at": (_now() + timedelta(days=D["ttl_days"])).isoformat()})
    D["set_cookie"](request, response, token)
    return {"step": "done", "username": username}


@router.get("/me")
async def me(request: Request):
    remote = is_remote(request)
    s = await session_doc(request) if remote else None
    ok = bool(s and s.get("remote"))
    return {"remote": remote, "signed_in": ok, "username": s.get("username") if ok else None}


@router.post("/logout")
async def logout(request: Request, response: Response):
    s = await session_doc(request)
    if s:
        await D["db"].sessions.delete_one({"token": s["token"]})
    response.delete_cookie(D["session_cookie"], path="/")
    return {"ok": True}


# ---------------------------------------------------------------- accounts (Settings, PIN-protected)

class NewUser(BaseModel):
    username: str
    name: Optional[str] = ""
    password: str


class NewPassword(BaseModel):
    password: str


def _check_password(pw: str):
    if len(pw) < MIN_PASSWORD:
        raise HTTPException(400, f"Password must be at least {MIN_PASSWORD} characters")


def _public(u: dict) -> dict:
    return {"id": str(u["_id"]), "username": u["username"], "name": u.get("name", ""),
            "two_factor": bool(u.get("totp_confirmed")), "created_at": u.get("created_at"),
            "last_login_at": u.get("last_login_at"), "last_login_ip": u.get("last_login_ip")}


async def _user(uid: str) -> dict:
    try:
        u = await D["db"].remote_users.find_one({"_id": ObjectId(uid)})
    except Exception:
        u = None
    if not u:
        raise HTTPException(404, "Login not found")
    return u


@router.get("/users")
async def list_users():
    return [_public(u) async for u in D["db"].remote_users.find().sort("created_at", 1)]


@router.post("/users")
async def create_user(req: NewUser):
    username = req.username.strip().lower()
    if not username.replace(".", "").replace("-", "").replace("_", "").isalnum() or not 3 <= len(username) <= 32:
        raise HTTPException(400, "Username: 3–32 letters or numbers (. - _ allowed)")
    _check_password(req.password)
    if await D["db"].remote_users.find_one({"username": username}):
        raise HTTPException(409, "That username is taken")
    doc = {"username": username, "name": (req.name or "").strip()[:60], "password_hash": hash_password(req.password),
           "totp_confirmed": False, "created_at": _now().isoformat()}
    res = await D["db"].remote_users.insert_one(doc)
    return _public({**doc, "_id": res.inserted_id})


async def _end_sessions(uid: str):
    await D["db"].sessions.delete_many({"remote": True, "user_id": uid})


@router.post("/users/{uid}/password")
async def set_password(uid: str, req: NewPassword):
    u = await _user(uid)
    _check_password(req.password)
    await D["db"].remote_users.update_one({"_id": u["_id"]}, {"$set": {"password_hash": hash_password(req.password)}})
    await _end_sessions(uid)
    return _public(u)


@router.post("/users/{uid}/reset-2fa")
async def reset_2fa(uid: str):
    u = await _user(uid)
    await D["db"].remote_users.update_one({"_id": u["_id"]}, {"$set": {"totp_confirmed": False},
                                                              "$unset": {"totp_secret": "", "last_step": ""}})
    await _end_sessions(uid)
    return _public({**u, "totp_confirmed": False})


@router.post("/users/{uid}/sign-out")
async def sign_out_everywhere(uid: str):
    await _user(uid)
    await _end_sessions(uid)
    return {"ok": True}


@router.delete("/users/{uid}")
async def delete_user(uid: str):
    u = await _user(uid)
    await D["db"].remote_users.delete_one({"_id": u["_id"]})
    await _end_sessions(uid)
    return {"ok": True}


async def init_indexes():
    await D["db"].remote_users.create_index("username", unique=True)
    await D["db"].login_attempts.create_index("identifier")
