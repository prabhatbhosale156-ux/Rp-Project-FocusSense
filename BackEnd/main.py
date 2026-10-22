from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Union
from datetime import datetime
import pandas as pd
import os
import sys

# Windows console Unicode safety: prevent unsupported characters
# in window titles/status messages from causing HTTP 500 errors.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass
import csv
import re
import hashlib
import secrets
import shutil
import json
import time
import threading
from groq import Groq

# =====================================================
# MONGODB
# =====================================================

from pymongo import MongoClient

# =====================================================
# =====================================================
# CLOUD AI - GROQ
# =====================================================

# Load a local .env automatically. This is important when FocusSense is
# started from Electron, a BAT launcher, or a packaged EXE because the
# Windows process may not inherit GROQ_API_KEY from the user's shell.
def _get_focussense_runtime_dir():

    # PyInstaller / packaged EXE: use the EXE folder.
    if getattr(sys, "frozen", False):
        return os.path.dirname(
            os.path.abspath(sys.executable)
        )

    # Normal Python source execution: use the main.py folder.
    return os.path.dirname(
        os.path.abspath(__file__)
    )


def _load_focussense_env_file():

    explicit_env = os.environ.get(
        "FOCUSENSE_ENV_FILE",
        ""
    ).strip()

    candidate_paths = []

    if explicit_env:
        candidate_paths.append(
            os.path.abspath(explicit_env)
        )

    runtime_dir = _get_focussense_runtime_dir()
    candidate_paths.append(
        os.path.join(runtime_dir, ".env")
    )

    # Also support starting main.py from another working directory.
    candidate_paths.append(
        os.path.join(os.getcwd(), ".env")
    )

    seen = set()

    for env_path in candidate_paths:

        env_path = os.path.abspath(env_path)

        if env_path in seen:
            continue

        seen.add(env_path)

        if not os.path.isfile(env_path):
            continue

        try:
            with open(
                env_path,
                "r",
                encoding="utf-8-sig"
            ) as env_file:

                for raw_line in env_file:

                    line = raw_line.strip()

                    if not line or line.startswith("#"):
                        continue

                    if line.lower().startswith("export "):
                        line = line[7:].strip()

                    if "=" not in line:
                        continue

                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    if not key:
                        continue

                    # Remove matching single/double quotes around values.
                    if (
                        len(value) >= 2
                        and value[0] == value[-1]
                        and value[0] in {'"', "'"}
                    ):
                        value = value[1:-1]

                    # Existing Windows environment variables take priority.
                    if not os.environ.get(key):
                        os.environ[key] = value

            return env_path

        except Exception as e:
            print(
                "FocusSense .env load error:",
                e
            )

    return ""


GROQ_ENV_FILE_PATH = _load_focussense_env_file()
GROQ_ENV_FILE_LOADED = bool(GROQ_ENV_FILE_PATH)

GROQ_API_KEY = os.environ.get(
    "GROQ_API_KEY",
    ""
).strip()

GROQ_MODEL = os.environ.get(
    "FOCUSENSE_GROQ_MODEL",
    "openai/gpt-oss-20b"
).strip()

# Keep the normal AI request and one retry inside the desktop collector's
# 15-second backend timeout.
GROQ_TIMEOUT_SECONDS = float(
    os.environ.get(
        "FOCUSENSE_GROQ_TIMEOUT",
        "6"
    )
)

GROQ_RETRY_COUNT = 1

# Avoid repeatedly calling Groq after a rate-limit/service failure.
# This is especially important for the desktop collector, which can
# generate many activity events during a study session.
GROQ_RATE_LIMIT_COOLDOWN_SECONDS = 120
groq_disabled_until = 0.0
groq_last_error = ""

GROQ_CLIENT = None

if GROQ_API_KEY:
    try:
        GROQ_CLIENT = Groq(
            api_key=GROQ_API_KEY,
            timeout=GROQ_TIMEOUT_SECONDS
        )
    except Exception as e:
        print(
            "Groq client initialization failed:",
            e
        )

# Activities shorter than this are not sent to the AI.
AI_MIN_DURATION_SECONDS = 0.0

# Reuse identical classifications for fifteen minutes.
# This reduces repeated cloud-AI calls when the same activity/window returns.
AI_CACHE_SECONDS = 900
ai_result_cache_by_user = {}

print("--------------------------------")
print("FocusSense Cloud AI Enabled")
print("AI Engine : Groq")
print("AI Model  :", GROQ_MODEL)
print("Groq API Key:", "AVAILABLE" if GROQ_API_KEY else "NOT FOUND")
print("Groq API Key Source:", GROQ_ENV_FILE_PATH if GROQ_ENV_FILE_PATH else "Windows environment")
print("Local .env Loaded:", "YES" if GROQ_ENV_FILE_LOADED else "NO")
print("Groq Timeout:", GROQ_TIMEOUT_SECONDS, "seconds")
print("Groq Retry Count:", GROQ_RETRY_COUNT)
print("AI Minimum Duration:", AI_MIN_DURATION_SECONDS, "seconds")
print("AI Classification Mode: Every detected activity")
print("AI Detection Classes: Productive / Distractive / Neutral")
print("AI Cache  :", f"{AI_CACHE_SECONDS} seconds")
print("--------------------------------")

MONGO_URI = "mongodb://localhost:27017"

mongo_client = None
mongo_db = None

activities_collection = None
study_sessions_collection = None
user_profile_collection = None
users_collection = None

MONGODB_CONNECTED = False

try:

    mongo_client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000
    )

    mongo_client.admin.command("ping")

    mongo_db = mongo_client["focussense"]

    activities_collection = mongo_db["activities"]
    study_sessions_collection = mongo_db["study_sessions"]
    user_profile_collection = mongo_db["user_profile"]
    users_collection = mongo_db["users"]

    MONGODB_CONNECTED = True

    print("--------------------------------")
    print("MongoDB Connected Successfully")
    print("Database: focussense")
    print("Collections:")
    print(" - activities")
    print(" - study_sessions")
    print(" - user_profile")
    print(" - users")
    print("--------------------------------")

except Exception as e:

    print("--------------------------------")
    print("MongoDB Connection Failed")
    print("Error:", e)
    print("--------------------------------")


def ensure_mongodb_connection():

    global mongo_client
    global mongo_db
    global activities_collection
    global study_sessions_collection
    global user_profile_collection
    global users_collection
    global MONGODB_CONNECTED

    if MONGODB_CONNECTED:

        try:

            mongo_client.admin.command(
                "ping"
            )

            return True

        except Exception as e:

            print(
                "MongoDB ping failed:",
                e
            )

            MONGODB_CONNECTED = False

    try:

        mongo_client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=3000
        )

        mongo_client.admin.command(
            "ping"
        )

        mongo_db = mongo_client[
            "focussense"
        ]

        activities_collection = mongo_db[
            "activities"
        ]

        study_sessions_collection = mongo_db[
            "study_sessions"
        ]

        user_profile_collection = mongo_db[
            "user_profile"
        ]

        users_collection = mongo_db[
            "users"
        ]

        MONGODB_CONNECTED = True

        print(
            "MongoDB reconnected successfully"
        )

        return True

    except Exception as e:

        MONGODB_CONNECTED = False

        print(
            "MongoDB reconnect failed:",
            e
        )

        return False


# =====================================================
# IMPORT PROJECT MODULES
# =====================================================

from activity_processor import process_activity
from distraction_engine import analyze_distraction
from recovery_engine import calculate_recovery
from distraction_cost import calculate_distraction_cost
from personal_model import update_personal_model, start_session


# =====================================================
# FASTAPI
# =====================================================

app = FastAPI(
    title="FocusSense API",
    description="Context-Aware Digital Study Behavior Intelligence",
    version="1.0.0"
)

# Swagger/OpenAPI Bearer authentication.
# This creates the Authorize button in /docs and makes Swagger
# automatically send: Authorization: Bearer <token>.
swagger_bearer = HTTPBearer(auto_error=False)


# =====================================================
# CORS
# =====================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================
# ACTIVITY MODEL
# =====================================================

class Activity(BaseModel):

    application: str
    window: str
    duration: float
    classification: Optional[str] = None

    # Optional exact timestamps supplied by the collector.  They may be
    # Unix seconds or an ISO/local datetime string.  When supplied, the
    # backend uses them directly so AI/network latency cannot move the
    # activity interval.
    start_time: Optional[Union[float, str]] = None
    end_time: Optional[Union[float, str]] = None
    timestamp: Optional[Union[float, str]] = None


# =====================================================
# STUDY SESSION MODEL
# =====================================================

class StudySession(BaseModel):

    subject: str
    goal: str
    duration: float


# =====================================================
# REGISTER MODEL
# =====================================================

class RegisterUser(BaseModel):

    username: str
    email: str
    password: str


# =====================================================
# LOGIN MODEL
# =====================================================

class LoginUser(BaseModel):

    email: str
    password: str


# =====================================================
# START STUDY SESSION MODEL
# =====================================================

class StartStudySession(BaseModel):

    subject: str = ""
    goal: str = ""


# =====================================================
# GLOBAL VARIABLES
# =====================================================

# Authentication/activity state is kept separately for each user.
active_user = None

previous_classification_by_user = {}

current_distraction_duration_by_user = {}

current_task_switches_by_user = {}

current_repeated_distractions_by_user = {}

latest_activity_by_user = {}

# Current study subject/goal for AI context.
active_study_context_by_user = {}

# Small recent activity sequence for contextual AI classification.
recent_activities_by_user = {}

# Latest AI classification details for each user.
ai_analysis_by_user = {}

# Profile statistics are measured from the user's latest successful login.
# Historical activity remains stored, but dashboard counters reset to zero
# at every new login and then count only activities from that login onward.
profile_session_start_by_user = {}

# Active study-session boundary used by the live dashboard/history.
# Activity before the current study session is kept in storage but is not
# shown in the current session history or counted in the live profile.
active_study_session_start_by_user = {}
active_study_session_number_by_user = {}

# True only while the current study session is running.
# The desktop collector may remain running in the background, but /activity
# records data only when this flag is True.
active_study_session_running_by_user = {}

# Protect session saving against repeated End clicks.  The lock prevents
# concurrent writes, while the recent-response cache makes a second/third
# identical request return the same successful result instead of creating a
# second session record.
study_session_save_lock = threading.Lock()
RECENT_SAVED_SESSION_SECONDS = 10
recent_saved_session_by_user = {}

# Small grace window for a collector request that is already in flight when
# the user clicks Start Study Session. Without this re-check, that first
# request can see the old "no session" state and be incorrectly marked
# LIVE ONLY even though the session starts a moment later.
SESSION_START_GRACE_SECONDS = 0.60

# Last persisted activity end time for each user.  If timestamps received
# from an older collector are within a tiny rounding window of the previous
# activity boundary, the new interval is aligned to the previous end.  This
# removes visible 1-second overlaps without changing activity duration.
last_saved_activity_end_by_user = {}

# Exact recorded-session recovery state.
# Stores the end timestamp of the most recent persisted Distractive activity.
last_distractive_end_by_user = {}

# Groq classification cache.
# The cache is keyed by user + current activity + study context.
# Recent activity is secondary context and must never override
# the current activity.
# The first classification comes from Groq AI.


# =====================================================
# AUTHENTICATION FUNCTIONS
# =====================================================

def hash_password(password):

    salt = secrets.token_hex(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000
    ).hex()

    return salt + ":" + password_hash


def verify_password(password, stored_password):

    try:

        salt, stored_hash = stored_password.split(":")

        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000
        ).hex()

        return secrets.compare_digest(
            password_hash,
            stored_hash
        )

    except Exception:

        return False


def create_token():

    return secrets.token_urlsafe(32)


def get_user_id(user):

    if not user or "_id" not in user:

        return None

    return str(user["_id"])


def get_current_user(authorization: str = Header(None)):

    global active_user

    if not authorization:

        raise HTTPException(
            status_code=401,
            detail="Authorization token required"
        )

    if not authorization.startswith("Bearer "):

        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format"
        )

    token = authorization.replace(
        "Bearer ",
        "",
        1
    ).strip()

    if not token:

        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

    if not ensure_mongodb_connection():

        raise HTTPException(
            status_code=500,
            detail="MongoDB is not connected"
        )

    try:

        # Keep _id because it is used internally as the stable user id.
        user = users_collection.find_one(
            {
                "token": token
            },
            {
                "password": 0
            }
        )

        if not user:

            raise HTTPException(
                status_code=401,
                detail="Invalid or expired login"
            )

        # The most recently authenticated user is used by the desktop
        # collector when it does not send an Authorization header.
        active_user = user

        # Keep the validated token available to the desktop collector.
        save_collector_token(token)

        return user

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


def get_request_user(
    authorization: str = None,
    required=True,
    allow_active=False
):

    global active_user

    if authorization:

        return get_current_user(
            authorization
        )

    if allow_active and active_user is not None:

        return active_user

    if required:

        raise HTTPException(
            status_code=401,
            detail="Authorization token required"
        )

    return None



# =====================================================
# COLLECTOR AUTHENTICATION TOKEN
# =====================================================

def get_collector_token_file():

    data_directory = os.environ.get(
        "FOCUSSENSE_DATA_DIR"
    )

    if not data_directory:

        data_directory = os.path.dirname(
            os.path.abspath(__file__)
        )

    os.makedirs(
        data_directory,
        exist_ok=True
    )

    return os.path.join(
        data_directory,
        "collector_token.txt"
    )


def clear_collector_token():

    token_file = get_collector_token_file()

    try:

        if os.path.exists(token_file):
            os.remove(token_file)

        return True

    except Exception as e:

        print(
            "Collector token clear error:",
            e
        )

        return False


def save_collector_token(token):

    token = str(token or "").strip()

    try:

        if not token:
            return clear_collector_token()

        token_file = get_collector_token_file()

        with open(
            token_file,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(token)
            file.flush()
            os.fsync(file.fileno())

        return True

    except Exception as e:

        print(
            "Collector token save error:",
            e
        )

        return False


def get_collector_token():

    token_file = get_collector_token_file()

    if not os.path.exists(token_file):
        return ""

    try:

        with open(
            token_file,
            "r",
            encoding="utf-8"
        ) as file:

            return file.read().strip()

    except Exception as e:

        print(
            "Collector token read error:",
            e
        )

        return ""



# =====================================================
# REGISTER
# =====================================================

@app.post("/register")
def register(user: RegisterUser):

    if not ensure_mongodb_connection():

        return {

            "status": "error",

            "message":
                "MongoDB is not connected"

        }

    username = user.username.strip()

    email = user.email.strip().lower()

    password = user.password

    if not username:

        return {

            "status": "error",

            "message":
                "Username is required"

        }

    if not email:

        return {

            "status": "error",

            "message":
                "Email is required"

        }

    if len(password) < 6:

        return {

            "status": "error",

            "message":
                "Password must contain at least 6 characters"

        }

    try:

        existing_user = users_collection.find_one(
            {
                "email": email
            }
        )

        if existing_user:

            return {

                "status": "error",

                "message":
                    "Email already registered"

            }

        existing_username = users_collection.find_one(
            {
                "username": username
            }
        )

        if existing_username:

            return {

                "status": "error",

                "message":
                    "Username already exists"

            }

        password_hash = hash_password(
            password
        )

        token = create_token()

        user_document = {

            "username":
                username,

            "email":
                email,

            "password":
                password_hash,

            "token":
                token,

            "created_at":
                datetime.now()

        }

        users_collection.insert_one(
            user_document
        )

        print("--------------------------------")
        print("NEW USER REGISTERED")
        print("Username:", username)
        print("Email:", email)
        print("--------------------------------")

        return {

            "status":
                "success",

            "message":
                "Registration successful",

            "user": {

                "username":
                    username,

                "email":
                    email

            }

        }

    except Exception as e:

        print(
            "Registration error:",
            e
        )

        return {

            "status":
                "error",

            "message":
                str(e)

        }


# =====================================================
# LOGIN
# =====================================================

@app.post("/login")
def login(user: LoginUser):

    global active_user

    if not ensure_mongodb_connection():

        return {

            "status": "error",

            "message": "MongoDB is not connected"

        }

    email = user.email.strip().lower()

    password = user.password

    try:

        existing_user = users_collection.find_one(
            {
                "email": email
            }
        )

        if not existing_user:

            return {

                "status": "error",

                "message": "Invalid email or password"

            }

        password_valid = verify_password(
            password,
            existing_user.get(
                "password",
                ""
            )
        )

        if not password_valid:

            return {

                "status": "error",

                "message": "Invalid email or password"

            }

        token = create_token()

        users_collection.update_one(
            {
                "_id": existing_user["_id"]
            },
            {
                "$set": {
                    "token": token,
                    "last_login": datetime.now()
                }
            }
        )

        # Make this user the active desktop collector user.
        active_user = dict(existing_user)
        active_user["token"] = token

        user_key = str(existing_user.get("_id", ""))
        user_id = get_user_id(existing_user)

        # -------------------------------------------------
        # RESET LIVE PROFILE FOR EVERY LOGIN
        # -------------------------------------------------
        # Historical activity is NOT deleted.  Only the live dashboard
        # statistics are reset by starting a fresh profile measurement
        # period at this login.
        profile_session_start_by_user[user_key] = datetime.now()
        active_study_session_start_by_user.pop(
            user_key,
            None
        )
        active_study_session_number_by_user.pop(
            user_key,
            None
        )
        active_study_session_running_by_user.pop(
            user_key,
            None
        )

        # A successful new login starts a fresh live measurement period.
        # Remove any old persisted active-session marker so it cannot be
        # restored accidentally for the new login.
        clear_active_study_session_state(
            user_id
        )

        last_saved_activity_end_by_user.pop(
            user_key,
            None
        )
        recent_saved_session_by_user.pop(
            user_key,
            None
        )

        previous_classification_by_user.pop(
            user_key,
            None
        )

        current_distraction_duration_by_user.pop(
            user_key,
            None
        )

        current_task_switches_by_user.pop(
            user_key,
            None
        )

        current_repeated_distractions_by_user.pop(
            user_key,
            None
        )

        active_study_context_by_user.pop(
            user_key,
            None
        )

        recent_activities_by_user.pop(
            user_key,
            None
        )

        ai_analysis_by_user.pop(
            user_key,
            None
        )

        latest_activity_by_user.pop(
            user_key,
            None
        )

        clear_ai_cache_for_user(existing_user.get("_id"))

        # Immediately store the reset profile so the dashboard starts at 0.
        reset_profile = build_user_profile(
            existing_user.get("_id")
        )

        save_profile_to_mongodb(
            existing_user.get("_id"),
            reset_profile
        )

        # Make the same login token available to the local collector.
        save_collector_token(token)

        print("--------------------------------")
        print("USER LOGIN SUCCESSFUL")
        print("Username:", existing_user["username"])
        print("Email:", existing_user["email"])
        print("--------------------------------")

        return {

            "status": "success",

            "message": "Login successful",

            "token": token,

            # Top-level fields keep compatibility with the current App.jsx.
            "username": existing_user["username"],
            "email": existing_user["email"],

            "user": {

                "username": existing_user["username"],

                "email": existing_user["email"]

            }

        }

    except Exception as e:

        print(
            "Login error:",
            e
        )

        return {

            "status": "error",

            "message": str(e)

        }


# =====================================================
# LOGOUT
# =====================================================

@app.post("/logout")
def logout(authorization: str = Header(None)):

    global active_user

    token = ""

    if authorization and authorization.startswith("Bearer "):

        token = authorization.replace(
            "Bearer ",
            "",
            1
        ).strip()

    if token and MONGODB_CONNECTED:

        try:

            users_collection.update_one(
                {
                    "token": token
                },
                {
                    "$set": {
                        "token": None
                    }
                }
            )

        except Exception as e:

            print(
                "Logout error:",
                e
            )

    if active_user is not None:

        active_user_id = get_user_id(
            active_user
        )

        if active_user_id is not None:

            active_key = str(
                active_user_id
            )

            active_study_context_by_user.pop(
                active_key,
                None
            )

            recent_activities_by_user.pop(
                active_key,
                None
            )

            ai_analysis_by_user.pop(
                active_key,
                None
            )

            profile_session_start_by_user.pop(
                active_key,
                None
            )

            active_study_session_start_by_user.pop(
                active_key,
                None
            )

            active_study_session_number_by_user.pop(
                active_key,
                None
            )
            active_study_session_running_by_user.pop(
                active_key,
                None
            )

            # Logout must also terminate persisted active-session recovery
            # state so the next login cannot inherit this session.
            clear_active_study_session_state(
                active_user_id
            )

            latest_activity_by_user.pop(
                active_key,
                None
            )
            last_saved_activity_end_by_user.pop(
                active_key,
                None
            )
            recent_saved_session_by_user.pop(
                active_key,
                None
            )

            previous_classification_by_user.pop(
                active_key,
                None
            )

            current_distraction_duration_by_user.pop(
                active_key,
                None
            )

            current_task_switches_by_user.pop(
                active_key,
                None
            )

            current_repeated_distractions_by_user.pop(
                active_key,
                None
            )

    # Prevent the collector from using the previous user's token.
    clear_collector_token()

    # Clear only the logged-out user's AI cache.
    if active_user is not None:
        clear_ai_cache_for_user(
            get_user_id(active_user)
        )
    else:
        clear_ai_cache_for_user()

    active_user = None

    return {

        "status": "success",

        "message": "Logout successful"

    }


# =====================================================
# CURRENT USER
# =====================================================

@app.get("/me")
def current_user(
    authorization: str = Header(None)
):

    user = get_current_user(
        authorization
    )

    username = user.get(
        "username",
        ""
    )

    email = user.get(
        "email",
        ""
    )

    return {

        "status": "success",

        # Top-level fields keep compatibility with the current App.jsx.
        "username": username,
        "email": email,

        "user": {

            "username": username,

            "email": email

        }

    }


# =====================================================
# CSV FILES
# =====================================================

DATA_DIR = os.environ.get(
    "FOCUSSENSE_DATA_DIR"
)

if not DATA_DIR:

    DATA_DIR = os.path.dirname(
        os.path.abspath(__file__)
    )

os.makedirs(
    DATA_DIR,
    exist_ok=True
)

BASE_DIR = DATA_DIR

CSV_FILE = os.path.join(
    DATA_DIR,
    "activity_log.csv"
)

STUDY_SESSIONS_FILE = os.path.join(
    DATA_DIR,
    "study_sessions.csv"
)


# =====================================================
# USER-SPECIFIC DATA STORAGE
# =====================================================

def get_user_data_dir(user_id):

    path = os.path.join(
        DATA_DIR,
        "users",
        str(user_id)
    )

    os.makedirs(
        path,
        exist_ok=True
    )

    return path


def get_user_activity_file(user_id):

    return os.path.join(
        get_user_data_dir(user_id),
        "activity_log.csv"
    )


def get_user_study_sessions_file(user_id):

    return os.path.join(
        get_user_data_dir(user_id),
        "study_sessions.csv"
    )


def get_user_active_session_file(user_id):
    return os.path.join(
        get_user_data_dir(user_id),
        "active_study_session.json"
    )


def save_active_study_session_state(
    user_id,
    session_number,
    subject,
    goal,
    session_started_at
):
    """Persist the active study-session boundary for collector recovery."""
    state_file = get_user_active_session_file(user_id)
    temp_file = state_file + ".tmp"

    state = {
        "session_number": int(session_number),
        "subject": str(subject or "").strip(),
        "goal": str(goal or "").strip(),
        "session_started_at": session_started_at.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    }

    try:
        with open(
            temp_file,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(state, file)
            file.flush()
            os.fsync(file.fileno())

        os.replace(
            temp_file,
            state_file
        )

        return True

    except Exception as e:
        print(
            "Active study-session state save error:",
            e
        )

        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception:
            pass

        return False


def load_active_study_session_state(user_id):
    state_file = get_user_active_session_file(user_id)

    if not os.path.exists(state_file):
        return None

    try:
        with open(
            state_file,
            "r",
            encoding="utf-8"
        ) as file:
            state = json.load(file)

        if not isinstance(state, dict):
            return None

        session_number = int(
            state.get("session_number")
        )

        session_started_at = datetime.strptime(
            str(state.get("session_started_at", "")).strip(),
            "%Y-%m-%d %H:%M:%S"
        )

        return {
            "session_number": session_number,
            "subject": str(
                state.get("subject", "")
            ).strip(),
            "goal": str(
                state.get("goal", "")
            ).strip(),
            "session_started_at": session_started_at
        }

    except Exception as e:
        print(
            "Active study-session state read error:",
            e
        )
        return None


def clear_active_study_session_state(user_id):
    state_file = get_user_active_session_file(user_id)

    try:
        if os.path.exists(state_file):
            os.remove(state_file)
    except Exception as e:
        print(
            "Active study-session state clear error:",
            e
        )


def restore_active_study_session_if_needed(user_id):
    user_key = str(user_id)

    if active_study_session_running_by_user.get(
        user_key,
        False
    ):
        return True

    state = load_active_study_session_state(
        user_id
    )

    if not state:
        return False

    active_study_session_number_by_user[
        user_key
    ] = state["session_number"]

    active_study_session_running_by_user[
        user_key
    ] = True

    active_study_session_start_by_user[
        user_key
    ] = state["session_started_at"]

    profile_session_start_by_user[
        user_key
    ] = state["session_started_at"]

    active_study_context_by_user[
        user_key
    ] = {
        "subject": state["subject"],
        "goal": state["goal"]
    }

    recent_activities_by_user.setdefault(
        user_key,
        []
    )

    # Recover the last persisted activity boundary so the first event after a
    # backend restart continues the same recorded timeline.
    try:
        session_items = get_saved_session_activities(
            user_id,
            str(state["session_number"])
        )

        if session_items:
            latest_end = None

            for item in session_items:
                parsed_end = parse_activity_datetime(
                    item.get("End Time", "")
                )

                if parsed_end is not None and (
                    latest_end is None or
                    parsed_end > latest_end
                ):
                    latest_end = parsed_end

            if latest_end is not None:
                last_saved_activity_end_by_user[
                    user_key
                ] = latest_end

    except Exception as e:
        print(
            "Active session activity-boundary restore error:",
            e
        )

    print("--------------------------------")
    print("ACTIVE STUDY SESSION RESTORED")
    print("Session:", state["session_number"])
    print("Subject:", state["subject"])
    print("Goal:", state["goal"])
    print("--------------------------------")

    return True


def legacy_migration_marker(user_id):

    return os.path.join(
        get_user_data_dir(user_id),
        ".legacy_migrated"
    )


def get_first_registered_user_id():

    if not MONGODB_CONNECTED:

        return None

    try:

        first_user = users_collection.find_one(
            {},
            {
                "_id": 1
            },
            sort=[("created_at", 1), ("_id", 1)]
        )

        if first_user:

            return str(first_user["_id"])

    except Exception as e:

        print(
            "Legacy owner lookup error:",
            e
        )

    return None


def migrate_legacy_data_for_user(user_id):

    """Assign old global data to the first registered account only.

    Existing project data is copied, never moved, so no original files are
    deleted during migration. A marker prevents cleared history from being
    copied back later.
    """

    marker = legacy_migration_marker(user_id)

    if os.path.exists(marker):

        return

    first_user_id = get_first_registered_user_id()

    if first_user_id != str(user_id):

        return

    user_dir = get_user_data_dir(user_id)

    legacy_activity = CSV_FILE
    legacy_sessions = STUDY_SESSIONS_FILE

    target_activity = get_user_activity_file(user_id)
    target_sessions = get_user_study_sessions_file(user_id)

    try:

        if os.path.exists(legacy_activity) and not os.path.exists(target_activity):

            shutil.copy2(
                legacy_activity,
                target_activity
            )

            print(
                "Migrated legacy activity CSV to user:",
                user_id
            )

        if os.path.exists(legacy_sessions) and not os.path.exists(target_sessions):

            shutil.copy2(
                legacy_sessions,
                target_sessions
            )

            print(
                "Migrated legacy study-session CSV to user:",
                user_id
            )

        # Old MongoDB records had no user_id. Assign them to the first
        # registered account so the original user's history is preserved.
        if MONGODB_CONNECTED:

            for collection in [
                activities_collection,
                study_sessions_collection,
                user_profile_collection
            ]:

                try:

                    collection.update_many(
                        {
                            "user_id": {
                                "$exists": False
                            }
                        },
                        {
                            "$set": {
                                "user_id": str(user_id)
                            }
                        }
                    )

                except Exception as e:

                    print(
                        "Legacy MongoDB migration error:",
                        e
                    )

        with open(
            marker,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(
                datetime.now().isoformat()
            )

    except Exception as e:

        print(
            "Legacy data migration error:",
            e
        )


def prepare_user_data(user_id):

    get_user_data_dir(user_id)

    migrate_legacy_data_for_user(user_id)

    return (
        get_user_activity_file(user_id),
        get_user_study_sessions_file(user_id)
    )


def read_user_activity_records(user_id):

    activity_file, _ = prepare_user_data(user_id)

    activities = []

    if not os.path.exists(activity_file):

        return activities

    try:

        with open(
            activity_file,
            "r",
            encoding="utf-8-sig",
            errors="replace",
            newline=""
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:

                if not row:
                    continue

                application = str(
                    row.get("Application", row.get("application", "Unknown")) or "Unknown"
                ).strip()

                window = str(
                    row.get("Window", row.get("window", "Unknown")) or "Unknown"
                ).strip()

                start_time = str(
                    row.get("Start Time", row.get("start_time", "")) or ""
                ).strip()

                end_time = str(
                    row.get("End Time", row.get("end_time", "")) or ""
                ).strip()

                duration_value = row.get(
                    "Duration (seconds)",
                    row.get("duration", 0)
                )

                try:
                    duration = float(duration_value or 0)
                except Exception:
                    duration = 0.0

                classification = str(
                    row.get("Classification", row.get("classification", "")) or ""
                ).strip()

                if not classification:
                    classification = "Neutral"

                recovery_value = row.get(
                    "Recovery Time",
                    row.get("recovery_time", 0)
                )

                try:
                    recovery_time = float(recovery_value or 0)
                except Exception:
                    recovery_time = 0.0

                task_switch_value = row.get(
                    "Task Switches",
                    row.get("task_switches", 0)
                )

                try:
                    task_switches = int(float(task_switch_value or 0))
                except Exception:
                    task_switches = 0

                activities.append({
                    "Application": application,
                    "Window": window,
                    "Start Time": start_time,
                    "End Time": end_time,
                    "Duration (seconds)": duration,
                    "Classification": classification,
                    "Recovery Time": recovery_time,
                    "Task Switches": task_switches,
                    "Distraction Pattern": str(
                        row.get("Distraction Pattern", "") or ""
                    ),
                    "Distraction Evidence": str(
                        row.get("Distraction Evidence", "") or ""
                    ),
                    "Distraction Cost Score": str(
                        row.get("Distraction Cost Score", "") or ""
                    ),
                    "Distraction Cost": str(
                        row.get("Distraction Cost", "") or ""
                    ),
                    "Study Session": str(
                        row.get("Study Session", "") or ""
                    ),
                    "Study Subject": str(
                        row.get("Study Subject", "") or ""
                    ),
                    "Study Goal": str(
                        row.get("Study Goal", "") or ""
                    )
                })

    except Exception as e:

        print(
            "User activity CSV reading error:",
            e
        )

    def parse_time(item):

        value = item.get("Start Time", "")

        try:
            result = pd.to_datetime(
                value,
                errors="coerce"
            )

            if pd.isna(result):
                return pd.Timestamp.min

            return result
        except Exception:
            return pd.Timestamp.min

    activities.sort(
        key=parse_time,
        reverse=True
    )

    return activities


def append_user_activity_to_csv(
    user_id,
    activity_data,
    recovery_time=0,
    task_switches=0
):

    activity_file, _ = prepare_user_data(user_id)

    file_exists = os.path.exists(activity_file)
    file_has_content = (
        file_exists and
        os.path.getsize(activity_file) > 0
    )

    duration = float(
        activity_data.get("duration", 0) or 0
    )

    # Prefer the timestamps captured when /activity received the event.
    # This prevents Groq/AI processing time from changing the displayed
    # activity interval. Fall back to deriving them only for older callers.
    end_time = None
    start_time = None

    end_value = str(
        activity_data.get("end_time", "") or ""
    ).strip()

    start_value = str(
        activity_data.get("start_time", "") or ""
    ).strip()

    if end_value:
        try:
            end_time = pd.to_datetime(
                end_value,
                errors="coerce"
            ).to_pydatetime()
        except Exception:
            end_time = None

    if start_value:
        try:
            start_time = pd.to_datetime(
                start_value,
                errors="coerce"
            ).to_pydatetime()
        except Exception:
            start_time = None

    if end_time is None:
        end_time = datetime.now()

    if start_time is None:
        start_time = datetime.fromtimestamp(
            end_time.timestamp() - max(duration, 0)
        )

    fieldnames = [
        "Application",
        "Window",
        "Start Time",
        "End Time",
        "Duration (seconds)",
        "Classification",
        "Recovery Time",
        "Task Switches",
        "Distraction Pattern",
        "Distraction Evidence",
        "Distraction Cost Score",
        "Distraction Cost",
        "Study Session",
        "Study Subject",
        "Study Goal"
    ]

    row = {
        "Application": activity_data.get("application", ""),
        "Window": activity_data.get("window", ""),
        "Start Time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "End Time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "Duration (seconds)": round(duration, 2),
        "Classification": activity_data.get("classification", "Neutral"),
        "Recovery Time": round(float(recovery_time or 0), 2),
        "Task Switches": int(task_switches or 0),
        "Distraction Pattern": activity_data.get("distraction", {}).get("pattern", "")
            if isinstance(activity_data.get("distraction"), dict) else "",
        "Distraction Evidence": activity_data.get("distraction", {}).get("evidence", "")
            if isinstance(activity_data.get("distraction"), dict) else "",
        "Distraction Cost Score": (
            activity_data.get("distraction_cost", {}).get("score", "")
            if isinstance(activity_data.get("distraction_cost"), dict) else ""
        ),
        "Distraction Cost": (
            activity_data.get("distraction_cost", {}).get("cost", "")
            if isinstance(activity_data.get("distraction_cost"), dict) else ""
        ),
        "Study Session": activity_data.get("study_session", ""),
        "Study Subject": activity_data.get("study_subject", ""),
        "Study Goal": activity_data.get("study_goal", "")
    }

    try:

        with open(
            activity_file,
            "a",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames
            )

            if not file_has_content:
                writer.writeheader()

            writer.writerow(row)
            file.flush()
            os.fsync(file.fileno())

        print("CSV SAVED:", activity_file)
        return True

    except Exception as e:

        print(
            "User activity CSV save error:",
            e
        )

        return False


def read_user_study_sessions(user_id):

    _, sessions_file = prepare_user_data(user_id)

    sessions = []

    if not os.path.exists(sessions_file):
        return sessions

    try:

        with open(
            sessions_file,
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:

                try:
                    duration = float(
                        row.get("Duration (seconds)", 0) or 0
                    )
                except Exception:
                    duration = 0.0

                sessions.append({
                    "session_number": str(
                        row.get("Session Number", "") or ""
                    ),
                    "subject": str(
                        row.get("Subject", "") or ""
                    ),
                    "goal": str(
                        row.get("Goal", "") or ""
                    ),
                    "duration": duration,
                    "date": str(
                        row.get("Date", "") or ""
                    ),
                    "time": str(
                        row.get("Time", "") or ""
                    )
                })

    except Exception as e:

        print(
            "User study-session CSV reading error:",
            e
        )

    sessions.sort(
        key=lambda item: int(item["session_number"])
        if str(item.get("session_number", "")).isdigit()
        else 0,
        reverse=True
    )

    return sessions


def normalize_study_session_record(item):
    """Normalize CSV/Mongo study-session records to one consistent shape."""
    if not isinstance(item, dict):
        return None

    session_number = str(
        item.get(
            "session_number",
            item.get("Session Number", "")
        ) or ""
    ).strip()

    if not session_number:
        return None

    subject = str(
        item.get(
            "subject",
            item.get("Subject", "")
        ) or ""
    ).strip()

    goal = str(
        item.get(
            "goal",
            item.get("Goal", "")
        ) or ""
    ).strip()

    duration_value = item.get(
        "duration",
        item.get("Duration (seconds)", 0)
    )

    try:
        duration = max(
            float(duration_value or 0),
            0.0
        )
    except Exception:
        duration = 0.0

    date = str(
        item.get(
            "date",
            item.get("Date", "")
        ) or ""
    ).strip()

    saved_time = str(
        item.get(
            "time",
            item.get("Time", "")
        ) or ""
    ).strip()

    # MongoDB may have created_at even when date/time fields are missing.
    created_at = item.get("created_at")

    if not date or not saved_time:
        try:
            if isinstance(created_at, datetime):
                created_dt = created_at
            else:
                created_dt = pd.to_datetime(
                    str(created_at or ""),
                    errors="coerce"
                )

                if pd.isna(created_dt):
                    created_dt = None
                else:
                    created_dt = created_dt.to_pydatetime()

            if created_dt is not None:
                if not date:
                    date = created_dt.strftime("%Y-%m-%d")
                if not saved_time:
                    saved_time = created_dt.strftime("%H:%M:%S")
        except Exception:
            pass

    return {
        "session_number": session_number,
        "subject": subject,
        "goal": goal,
        "duration": round(duration, 2),
        "date": date,
        "time": saved_time
    }


def get_unified_study_session_history(user_id):
    """Return one deduplicated study-session history from CSV + MongoDB.

    CSV is preferred when both stores contain the same session. MongoDB is
    used as a fallback and fills missing CSV metadata.
    """
    merged = {}

    # CSV remains the primary history source.
    try:
        for item in read_user_study_sessions(user_id):
            normalized = normalize_study_session_record(item)

            if normalized is not None:
                merged[normalized["session_number"]] = normalized

    except Exception as e:
        print(
            "Unified study-session CSV history error:",
            e
        )

    # MongoDB is a complement/fallback.
    if MONGODB_CONNECTED:
        try:
            documents = list(
                study_sessions_collection.find(
                    {
                        "user_id": str(user_id)
                    },
                    {
                        "_id": 0
                    }
                ).sort(
                    "created_at",
                    -1
                )
            )

            for item in documents:
                normalized = normalize_study_session_record(item)

                if normalized is None:
                    continue

                key = normalized["session_number"]

                if key not in merged:
                    merged[key] = normalized
                    continue

                # Same session in both stores: keep CSV values and fill
                # anything missing from MongoDB.
                existing = merged[key]

                for field in (
                    "subject",
                    "goal",
                    "date",
                    "time"
                ):
                    if not str(existing.get(field, "") or "").strip():
                        existing[field] = normalized.get(
                            field,
                            ""
                        )

                try:
                    existing_duration = float(
                        existing.get("duration", 0) or 0
                    )
                except Exception:
                    existing_duration = 0.0

                if (
                    existing_duration <= 0
                    and normalized.get("duration", 0) > 0
                ):
                    existing["duration"] = normalized["duration"]

        except Exception as e:
            print(
                "Unified study-session MongoDB history error:",
                e
            )

    sessions = list(
        merged.values()
    )

    def sort_key(item):
        number = str(
            item.get("session_number", "")
        ).strip()

        if number.isdigit():
            return (
                1,
                int(number)
            )

        try:
            combined = (
                str(item.get("date", "")).strip()
                + " "
                + str(item.get("time", "")).strip()
            )

            parsed = pd.to_datetime(
                combined,
                errors="coerce"
            )

            if pd.isna(parsed):
                return (
                    0,
                    0
                )

            return (
                0,
                parsed.timestamp()
            )

        except Exception:
            return (
                0,
                0
            )

    sessions.sort(
        key=sort_key,
        reverse=True
    )

    return sessions



def get_next_user_session_number(user_id):

    sessions = get_unified_study_session_history(
        user_id
    )

    highest = 0

    for session in sessions:

        try:
            number = int(
                session.get("session_number", 0)
            )

            highest = max(
                highest,
                number
            )

        except Exception:
            pass

    return highest + 1


def get_next_live_study_session_number(user_id):
    """Return a new live session number on every Start Session click."""

    user_key = str(user_id)
    next_saved_number = get_next_user_session_number(user_id)

    previous_live_number = active_study_session_number_by_user.get(
        user_key
    )

    if previous_live_number is None:
        return next_saved_number

    try:
        previous_live_number = int(previous_live_number)
    except Exception:
        return next_saved_number

    return max(
        next_saved_number,
        previous_live_number + 1
    )


def append_user_study_session_to_csv(
    user_id,
    session_number,
    subject,
    goal,
    duration,
    date,
    time
):

    _, sessions_file = prepare_user_data(user_id)

    file_exists = os.path.exists(sessions_file)
    file_has_content = (
        file_exists and
        os.path.getsize(sessions_file) > 0
    )

    fieldnames = [
        "Session Number",
        "Subject",
        "Goal",
        "Duration (seconds)",
        "Date",
        "Time"
    ]

    try:

        with open(
            sessions_file,
            "a",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames
            )

            if not file_has_content:
                writer.writeheader()

            writer.writerow({
                "Session Number": session_number,
                "Subject": str(subject).strip(),
                "Goal": str(goal).strip(),
                "Duration (seconds)": round(float(duration), 2),
                "Date": date,
                "Time": time
            })

            file.flush()
            os.fsync(file.fileno())

        return True

    except Exception as e:

        print(
            "User study-session CSV save error:",
            e
        )

        return False


def parse_activity_datetime(value):
    """Parse numeric/ISO/local datetime values into a datetime object."""
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value))
        except Exception:
            return None

    text = str(value).strip()
    if not text:
        return None

    # Numeric string -> Unix seconds.
    try:
        numeric = float(text)
        if text.replace('.', '', 1).replace('-', '', 1).isdigit():
            return datetime.fromtimestamp(numeric)
    except Exception:
        pass

    try:
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()
    except Exception:
        return None


def calculate_average_recovery_from_records(activities):
    """Calculate recovery from real activity boundaries, not cached values.

    Recovery is the elapsed time between the end of a Distractive activity
    and the start of the next Productive activity. Neutral activities do not
    reset the pending distraction, because the student may still be moving
    back toward the study task.
    """
    if not isinstance(activities, list) or not activities:
        return 0.0

    ordered = []
    for item in activities:
        start = parse_activity_datetime(
            item.get("Start Time") if isinstance(item, dict) else None
        ) or parse_activity_datetime(
            item.get("start_time") if isinstance(item, dict) else None
        )
        end = parse_activity_datetime(
            item.get("End Time") if isinstance(item, dict) else None
        ) or parse_activity_datetime(
            item.get("end_time") if isinstance(item, dict) else None
        )

        if start is None and end is not None:
            try:
                duration = max(
                    float(
                        item.get("Duration (seconds)", item.get("duration", 0))
                        if isinstance(item, dict)
                        else 0
                    ),
                    0.0
                )
            except Exception:
                duration = 0.0
            start = datetime.fromtimestamp(end.timestamp() - duration)

        if end is None and start is not None:
            try:
                duration = max(
                    float(
                        item.get("Duration (seconds)", item.get("duration", 0))
                        if isinstance(item, dict)
                        else 0
                    ),
                    0.0
                )
            except Exception:
                duration = 0.0
            end = datetime.fromtimestamp(start.timestamp() + duration)

        if start is None or end is None:
            continue

        classification = str(
            item.get("Classification", item.get("classification", "Neutral"))
            if isinstance(item, dict)
            else "Neutral"
        ).strip().lower()

        ordered.append((start, end, classification))

    ordered.sort(key=lambda value: value[0])

    recoveries = []
    last_distractive_end = None

    for start, end, classification in ordered:
        if classification == "distractive":
            last_distractive_end = end
            continue

        if classification == "productive" and last_distractive_end is not None:
            recovery = start.timestamp() - last_distractive_end.timestamp()
            if 0 <= recovery <= 3600:
                recoveries.append(recovery)
            last_distractive_end = None

    return (
        sum(recoveries) / len(recoveries)
        if recoveries
        else 0.0
    )


def calculate_recorded_session_duration_for_user(
    user_id,
    session_number,
    fallback_duration=0.0
):
    """Return wall-clock span of the requested session's recorded activities."""
    try:
        fallback = max(float(fallback_duration or 0), 0.0)
    except Exception:
        fallback = 0.0

    try:
        activities = read_user_activity_records(user_id)
    except Exception:
        activities = []

    target = str(session_number).strip()
    session_items = []

    for item in activities:
        item_session = str(
            item.get("Study Session", "") or
            item.get("study_session", "") or
            item.get("session_number", "") or
            ""
        ).strip()
        if item_session != target:
            continue

        start = parse_activity_datetime(
            item.get("Start Time") or item.get("start_time")
        )
        end = parse_activity_datetime(
            item.get("End Time") or item.get("end_time")
        )

        if start is None and end is not None:
            try:
                duration = max(
                    float(item.get("Duration (seconds)", item.get("duration", 0)) or 0),
                    0.0
                )
            except Exception:
                duration = 0.0
            start = datetime.fromtimestamp(end.timestamp() - duration)

        if end is None and start is not None:
            try:
                duration = max(
                    float(item.get("Duration (seconds)", item.get("duration", 0)) or 0),
                    0.0
                )
            except Exception:
                duration = 0.0
            end = datetime.fromtimestamp(start.timestamp() + duration)

        if start is not None and end is not None:
            session_items.append((start, end))

    if not session_items:
        return max(1, round(fallback)) if fallback > 0 else 0

    earliest_start = min(value[0] for value in session_items)
    latest_end = max(value[1] for value in session_items)
    recorded = max(0.0, latest_end.timestamp() - earliest_start.timestamp())

    # Use the recorded timeline when it exists.  The fallback is only used
    # when it is slightly longer and represents real elapsed session time.
    # This avoids ever saving a duration shorter than the UI timer.
    if fallback > recorded:
        recorded = fallback

    return max(1, round(recorded))


def build_user_profile(user_id):

    activities = read_user_activity_records(user_id)
    study_sessions = read_user_study_sessions(user_id)

    # The live profile follows the current login/study-session boundary.
    # When a study session is active, use the explicit Study Session field
    # first. This is more reliable than second-level timestamps for very
    # short activities because several events can occur within one second.
    profile_start = profile_session_start_by_user.get(
        str(user_id)
    )
    active_session_number = active_study_session_number_by_user.get(
        str(user_id)
    )

    if active_session_number is not None:

        filtered_activities = []

        for item in activities:

            item_session = str(
                item.get("Study Session", "") or ""
            ).strip()

            if item_session == str(active_session_number):
                filtered_activities.append(item)

        activities = filtered_activities

    elif profile_start is not None:

        filtered_activities = []

        for item in activities:

            end_value = str(
                item.get("End Time", "") or ""
            ).strip()

            start_value = str(
                item.get("Start Time", "") or ""
            ).strip()

            activity_time = None

            for value in (end_value, start_value):
                if not value:
                    continue
                try:
                    activity_time = datetime.strptime(
                        value,
                        "%Y-%m-%d %H:%M:%S"
                    )
                    break
                except Exception:
                    pass

            if activity_time is None:
                continue

            if activity_time >= profile_start:
                filtered_activities.append(item)

        activities = filtered_activities

    productive_time = 0.0
    distractive_time = 0.0
    total_distractions = 0
    task_switches = 0

    distraction_windows = []

    for item in activities:

        classification = str(
            item.get("Classification", "Neutral")
        ).strip().lower()

        try:
            duration = float(
                item.get("Duration (seconds)", 0) or 0
            )
        except Exception:
            duration = 0.0

        if classification == "productive":
            productive_time += duration

        elif classification == "distractive":
            distractive_time += duration
            total_distractions += 1

            window = str(
                item.get("Window", "") or ""
            ).strip()

            if window:
                distraction_windows.append(window)

        try:
            task_switches += int(
                float(item.get("Task Switches", 0) or 0)
            )
        except Exception:
            pass

    focus_time = (
        productive_time +
        distractive_time
    )

    productive_percentage = (
        (productive_time / focus_time) * 100
        if focus_time > 0
        else 0.0
    )

    # Always derive recovery from activity timestamps.  Stored per-row
    # recovery values may be stale after older versions of the application.
    average_recovery = calculate_average_recovery_from_records(activities)

    neutral_time = 0.0
    for item in activities:
        classification = str(
            item.get("Classification", "Neutral") or "Neutral"
        ).strip().lower()
        try:
            duration = float(
                item.get("Duration (seconds)", 0) or 0
            )
        except Exception:
            duration = 0.0
        if classification == "neutral":
            neutral_time += duration

    total_tracked_time = (
        productive_time +
        distractive_time +
        neutral_time
    )

    common_distraction = "None"

    if distraction_windows:

        from collections import Counter

        common_distraction = Counter(
            distraction_windows
        ).most_common(1)[0][0]

    return {
        "productive_time": round(productive_time, 2),
        "distractive_time": round(distractive_time, 2),
        "neutral_time": round(neutral_time, 2),
        "total_tracked_time": round(total_tracked_time, 2),
        "productive_percentage": round(productive_percentage, 2),
        "total_distractions": total_distractions,
        "average_recovery_time": round(average_recovery, 2),
        "task_switches": task_switches,
        "common_distraction": common_distraction,
        "sessions": len(study_sessions)
    }


# =====================================================
# CURRENT STUDY SESSION HISTORY HELPERS
# =====================================================

def get_current_study_session_start(user_id):

    return active_study_session_start_by_user.get(
        str(user_id)
    )


def filter_activities_for_current_study_session(
    user_id,
    activities
):

    session_start = get_current_study_session_start(
        user_id
    )

    if session_start is None:
        return []

    # Prefer the explicit session number. This keeps every tiny activity
    # recorded during the current session even when multiple activities
    # share the same second in their timestamps.
    active_session_number = active_study_session_number_by_user.get(
        str(user_id)
    )

    if active_session_number is not None:
        return [
            item
            for item in activities
            if str(item.get("Study Session", "") or "").strip()
            == str(active_session_number)
        ]

    filtered = []

    for item in activities:

        end_value = str(
            item.get("End Time", "") or ""
        ).strip()

        start_value = str(
            item.get("Start Time", "") or ""
        ).strip()

        activity_time = None

        for value in (end_value, start_value):
            if not value:
                continue

            try:
                activity_time = datetime.strptime(
                    value,
                    "%Y-%m-%d %H:%M:%S"
                )
                break
            except Exception:
                pass

        if activity_time is None:
            continue

        if activity_time >= session_start:
            filtered.append(item)

    return filtered


def get_current_study_context(user_id):

    user_key = str(user_id)

    context = active_study_context_by_user.get(
        user_key,
        {}
    )

    # Defensive guard: an invalid/stale session state must never cause
    # /activity to fail with a NoneType .get() error.
    if not isinstance(context, dict):
        context = {}

    return {
        "subject": str(
            context.get("subject", "")
            or ""
        ),
        "goal": str(
            context.get("goal", "")
            or ""
        ),
        "session_number": active_study_session_number_by_user.get(
            user_key
        ),
        "session_started_at": (
            active_study_session_start_by_user.get(
                user_key
            ).strftime("%Y-%m-%d %H:%M:%S")
            if active_study_session_start_by_user.get(
                user_key
            ) is not None
            else None
        )
    }


# =====================================================
# AI CLASSIFICATION - GROQ
# =====================================================

def _ai_cache_key(
    user_id,
    application,
    window,
    subject,
    goal
):

    return (
        str(user_id or "default"),
        str(application or "").strip().lower(),
        str(window or "").strip().lower(),
        str(subject or "").strip().lower(),
        str(goal or "").strip().lower()
    )


def clear_ai_cache_for_user(user_id=None):

    """Clear AI cache entries globally or only for one user."""

    if user_id is None:
        cleared = len(ai_result_cache_by_user)
        ai_result_cache_by_user.clear()
        return cleared

    user_key = str(user_id)
    keys_to_remove = []

    for key in list(ai_result_cache_by_user.keys()):
        if isinstance(key, tuple) and key:
            if str(key[0]) == user_key:
                keys_to_remove.append(key)

    for key in keys_to_remove:
        ai_result_cache_by_user.pop(key, None)

    return len(keys_to_remove)


def _normalize_confidence(value):

    try:
        confidence = float(value or 0)
    except Exception:
        confidence = 0.0

    if confidence > 1.0:
        confidence = confidence / 100.0

    return max(0.0, min(1.0, confidence))


def _local_fallback_classification(
    application,
    window,
    subject="",
    goal=""
):
    """Classify obvious activities locally when Groq is unavailable.

    This is used only as a classification fallback. It does not change
    activity persistence, study sessions, MongoDB, recovery, or dashboard
    behavior.
    """

    application = str(application or "").strip()
    window = str(window or "").strip()
    subject = str(subject or "").strip()
    goal = str(goal or "").strip()

    app_lower = application.lower()
    window_lower = window.lower()
    current_text = f"{app_lower} {window_lower}"
    study_text = f"{subject.lower()} {goal.lower()}"

    # System / task switching stays Neutral.
    neutral_patterns = (
        "task switching",
        "windows explorer",
        "file explorer",
        "desktop",
        "settings",
        "task manager",
        "start menu",
        "windows search",
        "screen snipping",
        "screen clipping",
        "unknown"
    )

    if (
        any(term in current_text for term in neutral_patterns)
        or app_lower in {
            "explorer.exe",
            "applicationframehost.exe",
            "searchapp.exe",
            "shellexperiencehost.exe",
            "screenclippinghost.exe"
        }
    ):
        return {
            "classification": "Neutral",
            "confidence": 0.99,
            "reason": "System or task-switching activity is neutral.",
            "pattern": "System activity",
            "evidence": f"{application} - {window}"
        }

    # Social / messaging / clearly recreational sites.
    distractive_patterns = (
        "whatsapp",
        "instagram",
        "facebook",
        "messenger",
        "snapchat",
        "telegram",
        "discord",
        "tiktok",
        "twitter",
        "x.com",
        "poki",
        "pokii",
        "friv",
        "crazygames",
        "miniclip",
        "roblox",
        "steam",
        "epic games",
        "netflix",
        "twitch",
        "shopping",
        "amazon",
        "flipkart",
        "youtube shorts",
        "shorts"
    )

    if any(term in current_text for term in distractive_patterns):
        return {
            "classification": "Distractive",
            "confidence": 0.99,
            "reason": "The current activity is clearly unrelated to the study task.",
            "pattern": "Known distracting activity",
            "evidence": f"{application} - {window}"
        }

    # Recreational games, except when the study context itself is about that game.
    game_patterns = (
        "euro truck simulator",
        "eurotrucks2",
        "grand theft auto",
        "gta v",
        "gta 5",
        "minecraft",
        "valorant",
        "counter-strike",
        "counter strike",
        "fortnite",
        "pubg",
        "gaming",
        "poki",
        "pokii",
        "friv",
        "crazygames",
        "miniclip",
        "roblox"
    )

    if (
        any(term in current_text for term in game_patterns)
        and not any(term in study_text for term in game_patterns)
    ):
        return {
            "classification": "Distractive",
            "confidence": 0.99,
            "reason": "Recreational gaming is unrelated to the current study task.",
            "pattern": "Recreational activity",
            "evidence": f"{application} - {window}"
        }

    # Coding IDEs are productive when a programming subject is active.
    language_map = {
        "python": (".py", "python"),
        "java": (".java", "java"),
        "javascript": (".js", "javascript", "node.js", "nodejs"),
        "typescript": (".ts", "typescript"),
        "c++": (".cpp", ".cc", ".cxx", "c++"),
        "cpp": (".cpp", ".cc", ".cxx", "c++"),
        "c": (".c", "c programming"),
        "html": (".html", ".htm", "html"),
        "css": (".css", "css"),
        "php": (".php", "php"),
        "sql": (".sql", "sql"),
        "kotlin": (".kt", "kotlin"),
        "swift": (".swift", "swift"),
        "dart": (".dart", "dart"),
        "go": (".go", "golang"),
        "rust": (".rs", "rust")
    }

    coding_apps = {
        "code.exe",
        "code",
        "netbeans64.exe",
        "netbeans.exe",
        "pycharm64.exe",
        "pycharm.exe",
        "idea64.exe",
        "eclipse.exe",
        "devenv.exe"
    }

    subject_key = subject.lower().strip()
    subject_terms = language_map.get(subject_key, ())

    if subject_terms:
        # A matching source file/window is productive.
        if any(term in window_lower for term in subject_terms):
            return {
                "classification": "Productive",
                "confidence": 0.99,
                "reason": f"Current activity directly supports the {subject} study.",
                "pattern": "Subject-relevant development activity",
                "evidence": f"{application} - {window}"
            }

        # IDE itself is productive for an active programming subject.
        if app_lower in coding_apps:
            return {
                "classification": "Productive",
                "confidence": 0.97,
                "reason": f"The current development environment supports the {subject} study.",
                "pattern": "Development environment",
                "evidence": f"{application} - {window}"
            }

    # Screen recording used for a study/project demonstration is productive.
    if (
        app_lower in {"bdcam.exe", "bdcam"}
        or "bandicam" in current_text
    ):
        return {
            "classification": "Productive",
            "confidence": 0.95,
            "reason": "Screen recording is being used to document or demonstrate the study project.",
            "pattern": "Study/demo recording activity",
            "evidence": f"{application} - {window}"
        }

    # Browser pages that clearly belong to the FocusSense/software project
    # are productive even when Groq is temporarily unavailable.
    # These markers are intentionally specific so ordinary browsing remains
    # eligible for AI/Neutral classification.
    focussense_project_markers = (
        "focussense",
        "fix stale session context",
        "frontend",
        "backend",
        "fastapi",
        "react",
        "vite",
        "mongodb",
        "uvicorn",
        "localhost",
        "api",
        "debugging",
        "debug",
        "programming",
        "coding",
        "developer",
        "development"
    )

    if (
        app_lower in {"msedge.exe", "chrome.exe", "firefox.exe", "brave.exe", "opera.exe"}
        and any(marker in current_text for marker in focussense_project_markers)
    ):
        return {
            "classification": "Productive",
            "confidence": 0.95,
            "reason": "The browser window clearly relates to the FocusSense software study project.",
            "pattern": "FocusSense project activity",
            "evidence": f"{application} - {window}"
        }

    # Generic development/documentation/research applications remain productive
    # when the current window clearly indicates educational work.
    productive_markers = (
        "visual studio code",
        "apache netbeans",
        "netbeans",
        "pycharm",
        "intellij idea",
        "eclipse",
        "jupyter",
        "documentation",
        "tutorial",
        "geeksforgeeks",
        "w3schools",
        "stackoverflow",
        "stack overflow",
        "github",
        "research paper",
        "assignment",
        "project"
    )

    if any(marker in current_text for marker in productive_markers):
        return {
            "classification": "Productive",
            "confidence": 0.90,
            "reason": "The current activity appears related to learning or development.",
            "pattern": "Educational/development activity",
            "evidence": f"{application} - {window}"
        }

    # Keep genuinely ambiguous activities neutral rather than guessing.
    # This result is also safe to use when cloud AI is temporarily unavailable.
    return {
        "classification": "Neutral",
        "confidence": 0.25,
        "reason": "The current activity is ambiguous from its application and window context.",
        "pattern": "Local semantic fallback",
        "evidence": f"{application} - {window}"
    }


def _safe_local_result_for_ai_issue(local_result, issue=""):
    """Return a clean local result without exposing cloud-AI failure wording."""
    result = dict(local_result or {})

    if str(result.get("pattern", "")).strip() in {
        "Local fallback",
        "Local semantic fallback"
    }:
        result["pattern"] = "Local semantic fallback"

        # Do not claim the activity is productive/distractive when it is
        # genuinely ambiguous. Keep the original neutral confidence.
        if str(result.get("classification", "Neutral")).strip() == "Neutral":
            result["confidence"] = min(
                float(result.get("confidence", 0.25) or 0.25),
                0.25
            )
            result["reason"] = (
                "The current activity is ambiguous from its application "
                "and window context."
            )

    return result


def _groq_is_rate_limited(error):
    """Detect Groq 429/rate-limit failures without depending on SDK version."""
    status_code = getattr(error, "status_code", None)
    if status_code == 429:
        return True

    text = str(error or "").lower()

    rate_terms = (
        "429",
        "rate limit",
        "rate_limit",
        "too many requests",
        "tokens per day",
        "token limit",
        "limit reached"
    )

    return any(term in text for term in rate_terms)


def classify_activity_with_ai(
    application,
    window,
    duration,
    subject="",
    goal="",
    recent_activities=None,
    user_id=None
):

    global groq_disabled_until
    global groq_last_error

    application = str(application or "").strip()
    window = str(window or "").strip()
    subject = str(subject or "").strip()
    goal = str(goal or "").strip()

    try:
        duration = float(duration or 0)
    except Exception:
        duration = 0.0

    if recent_activities is None:
        recent_activities = []

    # Existing behavior: every non-negative activity can be classified.
    if duration < 0:
        return {
            "classification": "Neutral",
            "confidence": 0.0,
            "reason": "Invalid activity duration.",
            "pattern": "Invalid duration",
            "evidence": f"{application} - {window}"
        }

    app_lower = application.lower()
    window_lower = window.lower()
    subject_lower = subject.lower()
    goal_lower = goal.lower()
    current_text = f"{app_lower} {window_lower}"

    # Clear, deterministic classification first. These rules only affect
    # classification and avoid spending Groq tokens on obvious cases.
    local_result = _local_fallback_classification(
        application,
        window,
        subject,
        goal
    )

    # Use local result immediately for unambiguous classes.
    if local_result.get("classification") in {"Productive", "Distractive"}:
        return local_result

    # System activity is always neutral and should not be sent to Groq.
    if local_result.get("pattern") == "System activity":
        return local_result

    cache_key = _ai_cache_key(
        user_id,
        application,
        window,
        subject,
        goal
    )

    now = time.time()
    cached_item = ai_result_cache_by_user.get(cache_key)

    if isinstance(cached_item, dict):
        cached_result = cached_item.get("result")
        if (
            isinstance(cached_result, dict)
            and now - float(cached_item.get("time", 0) or 0) <= AI_CACHE_SECONDS
        ):
            print("--------------------------------")
            print("GROQ AI CACHE HIT")
            print("Application:", application)
            print("Window:", window)
            print("Classification:", cached_result.get("classification", "Neutral"))
            print("--------------------------------")
            return dict(cached_result)

    # No configured cloud client: use the same deterministic local
    # classification without breaking the activity pipeline.
    if not GROQ_API_KEY or GROQ_CLIENT is None:
        print("--------------------------------")
        print("CLOUD AI CLIENT NOT READY")
        print("Using local semantic classification.")
        print("--------------------------------")
        return _safe_local_result_for_ai_issue(local_result, "client")

    # Circuit breaker: after a Groq rate-limit/service failure, do not keep
    # hammering the API for every activity. Local classification continues
    # immediately and Groq is retried automatically after the cooldown.
    if time.time() < groq_disabled_until:
        return _safe_local_result_for_ai_issue(local_result, "cooldown")

    recent = []
    if isinstance(recent_activities, list):
        for item in recent_activities[-2:]:
            if isinstance(item, dict):
                recent.append({
                    "application": str(item.get("application", "")),
                    "window": str(item.get("window", "")),
                    "classification": str(item.get("classification", ""))
                })

    recent_text = json.dumps(
        recent,
        ensure_ascii=False,
        separators=(",", ":")
    )

    system_prompt = """
You are FocusSense. Classify ONLY the CURRENT computer activity as
Productive, Distractive, or Neutral using the current study context.

PRIMARY EVIDENCE:
1. Current application
2. Current window title

SECONDARY EVIDENCE:
3. Study subject
4. Study goal
5. Duration
6. Recent activities only as secondary context

STRICT RULES:
- Productive = the CURRENT activity directly supports the current subject
  or goal: coding, editing the relevant source file, relevant documentation,
  relevant search, relevant tutorial, assignment/project work, or educational
  content related to the study.
- Distractive = the CURRENT activity is clearly unrelated to the current
  subject/goal: social media, messaging, recreational games, entertainment,
  unrelated browsing, shopping, etc.
- Neutral = system activity, Task Switching, file management, desktop/system
  dialogs, or genuinely ambiguous activity.
- Do NOT classify an application alone. Use the CURRENT window title.
- Do NOT use recent activity to override clear evidence from the CURRENT activity.
- If the window clearly contains the current subject, a relevant programming
  language/file extension, or a relevant tutorial/documentation/search, prefer
  Productive.
- If the window clearly shows social media/messaging or recreational gaming,
  prefer Distractive.
- If evidence is genuinely insufficient, use Neutral.
- Do not infer emotions, motivation, mental health, or psychological state.
- Do not invent facts.

Return ONLY one valid JSON object with exactly these five keys:
classification, confidence, reason, pattern, evidence

classification must be exactly Productive, Distractive, or Neutral.
confidence must be a number from 0 to 1.
reason must be a short string (20 words or fewer).
pattern must be a short string.
evidence must be a short string, never an array.
Do not include markdown, code fences, extra keys, or extra text.
"""

    user_prompt = f"""
CURRENT ACTIVITY:
Application: {application}
Window: {window}
Duration: {duration:.1f} seconds

STUDY CONTEXT:
Subject: {subject or "Not specified"}
Goal: {goal or "Not specified"}

RECENT ACTIVITY (secondary only):
{recent_text}

Classify the CURRENT activity only.
"""

    try:
        response = None
        last_error = None

        for attempt in range(GROQ_RETRY_COUNT + 1):
            try:
                response = GROQ_CLIENT.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0,
                    max_completion_tokens=320,
                    include_reasoning=False
                )
                break

            except Exception as request_error:
                last_error = request_error

                print("--------------------------------")
                print("GROQ REQUEST ATTEMPT FAILED")
                print("Attempt:", attempt + 1, "of", GROQ_RETRY_COUNT + 1)
                print("Error:", request_error)
                print("--------------------------------")

                # A 429 should never be retried immediately. That only
                # increases pressure on an already limited API.
                if _groq_is_rate_limited(request_error):
                    groq_disabled_until = (
                        time.time() + GROQ_RATE_LIMIT_COOLDOWN_SECONDS
                    )
                    groq_last_error = str(request_error)

                    print("--------------------------------")
                    print("GROQ RATE LIMIT DETECTED")
                    print(
                        "Local semantic classification will be used for "
                        f"{GROQ_RATE_LIMIT_COOLDOWN_SECONDS} seconds."
                    )
                    print("--------------------------------")

                    return _safe_local_result_for_ai_issue(
                        local_result,
                        "rate_limit"
                    )

                if attempt >= GROQ_RETRY_COUNT:
                    raise

                # Small pause for transient network/server errors.
                time.sleep(0.35)

        if response is None:
            raise last_error or RuntimeError(
                "Groq returned no response object."
            )

        raw_output = (
            response.choices[0].message.content
            or ""
        ).strip()

        print("--------------------------------")
        print("GROQ AI RESULT")
        print("Application:", application)
        print("Window:", window)
        print("Raw:", raw_output)
        print("--------------------------------")

        if not raw_output:
            raise ValueError("Groq returned an empty response.")

        cleaned = raw_output.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            start_pos = cleaned.find("{")
            end_pos = cleaned.rfind("}")
            if start_pos >= 0 and end_pos > start_pos:
                result = json.loads(cleaned[start_pos:end_pos + 1])
            else:
                raise

        if not isinstance(result, dict):
            raise ValueError("Groq returned a non-object JSON response.")

        classification_map = {
            "productive": "Productive",
            "distractive": "Distractive",
            "neutral": "Neutral"
        }

        classification = classification_map.get(
            str(result.get("classification", "Neutral")).strip().lower(),
            "Neutral"
        )

        confidence = _normalize_confidence(result.get("confidence", 0))

        ai_result = {
            "classification": classification,
            "confidence": round(confidence, 3),
            "reason": str(result.get("reason", "")).strip()[:180],
            "pattern": str(result.get("pattern", "")).strip()[:180],
            "evidence": str(
                result.get("evidence", f"{application} - {window}")
            ).strip()[:200]
        }

        groq_disabled_until = 0.0
        groq_last_error = ""

        ai_result_cache_by_user[cache_key] = {
            "time": now,
            "result": dict(ai_result)
        }

        if len(ai_result_cache_by_user) > 200:
            oldest_key = min(
                ai_result_cache_by_user,
                key=lambda key: ai_result_cache_by_user[key].get("time", 0)
            )
            ai_result_cache_by_user.pop(oldest_key, None)

        print("--------------------------------")
        print("FOCUSENSE AI CLASSIFICATION")
        print("Classification:", ai_result["classification"])
        print("AI Confidence:", ai_result["confidence"])
        print("AI Reason:", ai_result["reason"])
        print("AI Pattern:", ai_result["pattern"])
        print("AI Evidence:", ai_result["evidence"])
        print("--------------------------------")
        return ai_result

    except Exception as e:
        groq_last_error = str(e)

        # For temporary cloud/API/format failures, keep the activity pipeline
        # running and classify locally instead of producing an AI-availability
        # error result or interrupting CSV/MongoDB persistence.
        print("--------------------------------")
        print("GROQ AI TEMPORARILY UNAVAILABLE")
        print("Error:", e)
        print("Continuing with local semantic classification.")
        print("--------------------------------")

        return _safe_local_result_for_ai_issue(
            local_result,
            "error"
        )

def get_classification(
    application,
    window,
    duration,
    user_id=None
):

    user_key = (
        str(user_id)
        if user_id is not None
        else "default"
    )

    context = active_study_context_by_user.get(
        user_key,
        {}
    )

    if not isinstance(context, dict):
        context = {}

    recent = recent_activities_by_user.get(
        user_key,
        []
    )

    ai_result = classify_activity_with_ai(
        application=application,
        window=window,
        duration=duration,
        subject=context.get("subject", ""),
        goal=context.get("goal", ""),
        recent_activities=recent,
        user_id=user_id
    )

    # Defensive guard: the AI engine must always produce a dictionary.
    # If a future provider/client path accidentally returns None, keep the
    # activity processable instead of raising a NoneType .get() error.
    if not isinstance(ai_result, dict):
        ai_result = {
            "classification": "Neutral",
            "confidence": 0.0,
            "reason": "AI returned no usable classification.",
            "pattern": "AI response error",
            "evidence": f"{application} - {window}"
        }

    ai_analysis_by_user[user_key] = ai_result

    return ai_result.get(
        "classification",
        "Neutral"
    )


# =====================================================
# MONGODB CONNECTION STATUS
# =====================================================

@app.get("/mongodb-status")
def mongodb_status():

    if ensure_mongodb_connection():

        return {

            "status":
                "success",

            "mongodb":
                "connected",

            "database":
                "focussense",

            "collections": [

                "activities",

                "study_sessions",

                "user_profile",

                "users"

            ]

        }

    return {

        "status":
            "error",

        "mongodb":
            "not connected"

    }


# =====================================================
# READ ACTIVITY CSV SAFELY
# =====================================================

def read_activity_csv():

    activities = []

    if not os.path.exists(
        CSV_FILE
    ):

        return activities

    try:

        with open(
            CSV_FILE,
            "r",
            encoding="utf-8-sig",
            errors="replace",
            newline=""
        ) as file:

            reader = csv.reader(
                file
            )

            for row in reader:

                if not row:

                    continue

                if (
                    row[0]
                    .strip()
                    .lower()
                    == "application"
                ):

                    continue

                if len(row) < 5:

                    continue

                application = row[0].strip()

                date_index = None

                # =================================================
                # FIND DATE COLUMN
                # =================================================

                for i in range(
                    1,
                    len(row) - 2
                ):

                    value = row[i].strip()

                    if (
                        len(value) >= 10
                        and value[0:4].isdigit()
                        and value[4] == "-"
                    ):

                        date_index = i

                        break

                    if "/" in value:

                        parts = value.split("/")

                        if len(parts) == 3:

                            date_index = i

                            break

                if date_index is None:

                    continue

                window = ",".join(
                    row[1:date_index]
                ).strip()

                if len(row) <= date_index + 2:

                    continue

                start_time = row[
                    date_index
                ].strip()

                end_time = row[
                    date_index + 1
                ].strip()

                duration = row[
                    date_index + 2
                ].strip()

                try:

                    duration_float = float(
                        duration
                    )

                except:

                    duration_float = 0.0

                classification = "Neutral"

                activities.append({

                    "Application":
                        application,

                    "Window":
                        window,

                    "Start Time":
                        start_time,

                    "End Time":
                        end_time,

                    "Duration (seconds)":
                        duration_float,

                    "Classification":
                        classification

                })

    except Exception as e:

        print(
            "CSV reading error:",
            e
        )

    return activities


# =====================================================
# GET NEXT STUDY SESSION NUMBER
# =====================================================

def get_next_session_number():

    next_number = 1

    if not os.path.exists(
        STUDY_SESSIONS_FILE
    ):

        return next_number

    try:

        with open(
            STUDY_SESSIONS_FILE,
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            reader = csv.DictReader(
                file
            )

            highest_number = 0

            for row in reader:

                value = row.get(
                    "Session Number",
                    ""
                )

                try:

                    number = int(
                        str(value).strip()
                    )

                    if number > highest_number:

                        highest_number = number

                except:

                    pass

            next_number = (
                highest_number + 1
            )

    except Exception as e:

        print(
            "Session number read error:",
            e
        )

        next_number = 1

    return next_number


# =====================================================
# CURRENT STUDY CONTEXT
# =====================================================

@app.get("/current-study-context")
def current_study_context(
    authorization: str = Header(None)
):

    user = get_request_user(
        authorization,
        required=True
    )

    user_id = get_user_id(user)
    user_key = str(user_id)

    context = active_study_context_by_user.get(
        user_key,
        {}
    )

    return {
        "status": "success",
        "active": active_study_session_running_by_user.get(user_key, False),
        "subject": context.get("subject", ""),
        "goal": context.get("goal", ""),
        "session_number": active_study_session_number_by_user.get(user_key),
        "session_running": active_study_session_running_by_user.get(user_key, False)
    }


# =====================================================
# SAVE STUDY SESSION TO CSV
# =====================================================

def save_study_session_to_csv(
    subject,
    goal,
    duration
):

    print(
        "=========================================="
    )

    print(
        "SAVING STUDY SESSION"
    )

    print(
        "CSV FILE:"
    )

    print(
        STUDY_SESSIONS_FILE
    )

    os.makedirs(
        BASE_DIR,
        exist_ok=True
    )

    file_exists = os.path.exists(
        STUDY_SESSIONS_FILE
    )

    file_has_content = (
        file_exists
        and os.path.getsize(
            STUDY_SESSIONS_FILE
        ) > 0
    )

    session_number = (
        get_next_session_number()
    )

    now = datetime.now()

    date = now.strftime(
        "%Y-%m-%d"
    )

    time = now.strftime(
        "%H:%M:%S"
    )

    row = [

        session_number,

        str(subject).strip(),

        str(goal).strip(),

        round(
            float(duration),
            2
        ),

        date,

        time

    ]

    try:

        with open(
            STUDY_SESSIONS_FILE,
            "a",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            writer = csv.writer(
                file
            )

            if not file_has_content:

                writer.writerow([

                    "Session Number",

                    "Subject",

                    "Goal",

                    "Duration (seconds)",

                    "Date",

                    "Time"

                ])

            writer.writerow(
                row
            )

            file.flush()

            os.fsync(
                file.fileno()
            )

        print(
            "SESSION SAVED SUCCESSFULLY"
        )

        print(
            "Session Number:",
            session_number
        )

        print(
            "Subject:",
            subject
        )

        print(
            "Goal:",
            goal
        )

        print(
            "Duration:",
            duration,
            "seconds"
        )

        print(
            "Date:",
            date
        )

        print(
            "Time:",
            time
        )

        print(
            "Saved CSV:",
            STUDY_SESSIONS_FILE
        )

        print(
            "=========================================="
        )

        return session_number

    except Exception as e:

        print(
            "=========================================="
        )

        print(
            "ERROR SAVING STUDY SESSION"
        )

        print(
            "Error:",
            e
        )

        print(
            "CSV Path:",
            STUDY_SESSIONS_FILE
        )

        print(
            "=========================================="
        )

        return None


# =====================================================
# SAVE ACTIVITY TO MONGODB
# =====================================================

def save_activity_to_mongodb(
    user_id,
    activity_data
):

    if not ensure_mongodb_connection():
        return False

    try:

        document = dict(activity_data)
        document["user_id"] = str(user_id)
        document["created_at"] = datetime.now()

        if activities_collection is None:
            print(
                "MongoDB activity save error: activities collection is not initialized"
            )
            return False

        insert_result = activities_collection.insert_one(
            document
        )

        if not insert_result.acknowledged:
            print(
                "MongoDB activity save FAILED: insert was not acknowledged"
            )
            return False

        print(
            "✓ Activity saved to MongoDB for user:",
            user_id
        )
        print(
            "✓ MongoDB collection: activities"
        )
        print(
            "✓ MongoDB document ID:",
            str(insert_result.inserted_id)
        )

        return True

    except Exception as e:

        print(
            "MongoDB activity save error:",
            e
        )

        return False


# =====================================================
# SAVE STUDY SESSION TO MONGODB
# =====================================================

def save_study_session_to_mongodb(
    user_id,
    session_number,
    subject,
    goal,
    duration,
    date,
    time
):

    if not ensure_mongodb_connection():
        return False

    try:

        document = {
            "user_id": str(user_id),
            "session_number": session_number,
            "subject": str(subject).strip(),
            "goal": str(goal).strip(),
            "duration": float(duration),
            "date": date,
            "time": time,
            "created_at": datetime.now()
        }

        result = study_sessions_collection.update_one(
            {
                "user_id": str(user_id),
                "session_number": session_number
            },
            {
                "$set": document
            },
            upsert=True
        )

        print(
            "Study session saved to MongoDB for user:",
            user_id
        )

        print(
            "MongoDB session upsert acknowledged:",
            result.acknowledged
        )

        return bool(
            result.acknowledged
        )

    except Exception as e:

        print(
            "MongoDB study session save error:",
            e
        )

        return False


# =====================================================
# SAVE PERSONAL PROFILE TO MONGODB
# =====================================================

def save_profile_to_mongodb(
    user_id,
    profile
):

    if not ensure_mongodb_connection():
        return False

    if not isinstance(profile, dict):
        return False

    try:

        profile_document = dict(profile)
        profile_document["user_id"] = str(user_id)
        profile_document["updated_at"] = datetime.now()

        user_profile_collection.update_one(
            {
                "user_id": str(user_id)
            },
            {
                "$set": profile_document
            },
            upsert=True
        )

        print(
            "Personal profile saved to MongoDB for user:",
            user_id
        )

        return True

    except Exception as e:

        print(
            "MongoDB profile save error:",
            e
        )

        return False


# =====================================================
# AI STATUS
# =====================================================

@app.get("/ai-status")
def ai_status():

    configured = bool(
        GROQ_API_KEY
        and GROQ_CLIENT is not None
    )

    return {
        "status": "success" if configured else "error",
        "engine": "Groq",
        "model": GROQ_MODEL,
        "groq": "configured" if configured else "not configured",
        "api_key_available": bool(GROQ_API_KEY),
        "timeout_seconds": GROQ_TIMEOUT_SECONDS,
        "cache_seconds": AI_CACHE_SECONDS,
        "rate_limit_cooldown_seconds": GROQ_RATE_LIMIT_COOLDOWN_SECONDS,
        "cloud_ai_cooldown_active": time.time() < groq_disabled_until,
        "message": (
            "Groq AI is configured and ready."
            if configured
            else "Set GROQ_API_KEY and restart FocusSense."
        )
    }


# =====================================================
# START SESSION
# =====================================================

@app.post("/start-session")
def begin_session(
    session: Optional[StartStudySession] = None,
    authorization: str = Header(None)
):

    user = get_request_user(
        authorization,
        required=True
    )

    user_id = get_user_id(user)
    user_key = str(user_id)

    # -------------------------------------------------
    # SAVE CURRENT STUDY CONTEXT FOR AI
    # -------------------------------------------------

    subject = ""
    goal = ""

    if session is not None:

        subject = str(
            session.subject or ""
        ).strip()

        goal = str(
            session.goal or ""
        ).strip()

    active_study_context_by_user[
        user_key
    ] = {
        "subject": subject,
        "goal": goal
    }

    # -------------------------------------------------
    # RESET LIVE PROFILE + HISTORY FOR THIS STUDY SESSION
    # -------------------------------------------------
    session_started_at = datetime.now()

    profile_session_start_by_user[user_key] = session_started_at
    active_study_session_start_by_user[user_key] = session_started_at

    previous_classification_by_user.pop(
        user_key,
        None
    )

    current_distraction_duration_by_user.pop(
        user_key,
        None
    )

    current_task_switches_by_user.pop(
        user_key,
        None
    )

    current_repeated_distractions_by_user.pop(
        user_key,
        None
    )

    latest_activity_by_user.pop(
        user_key,
        None
    )

    recent_activities_by_user[
        user_key
    ] = []

    ai_analysis_by_user.pop(
        user_key,
        None
    )

    # A new study session changes the semantic context. Never reuse an AI
    # result from an earlier session, even when the subject/goal strings
    # happen to be identical.
    cleared_cache_entries = clear_ai_cache_for_user(
        user_id
    )

    # IMPORTANT: every Start Session click creates a new live session number.
    # This prevents an unsaved previous session from sharing the same number.
    session_number = get_next_live_study_session_number(
        user_id
    )

    active_study_session_number_by_user[user_key] = session_number
    active_study_session_running_by_user[user_key] = True

    save_active_study_session_state(
        user_id,
        session_number,
        subject,
        goal,
        session_started_at
    )

    last_saved_activity_end_by_user.pop(
        user_key,
        None
    )
    last_distractive_end_by_user.pop(
        user_key,
        None
    )
    recent_saved_session_by_user.pop(
        user_key,
        None
    )

    # Store a clean zeroed profile immediately. As activity arrives, the
    # profile will be rebuilt from this study-session boundary.
    reset_profile = build_user_profile(
        user_id
    )

    save_profile_to_mongodb(
        user_id,
        reset_profile
    )

    print("--------------------------------")
    print("STUDY SESSION STARTED")
    print("User:", user.get("username", ""))
    print("Session:", session_number)
    print("Subject:", subject)
    print("Goal:", goal)
    print("AI Cache Entries Cleared:", cleared_cache_entries)
    print("--------------------------------")

    return {
        "status": "success",
        "message": "Study session started",
        "session": session_number,
        "subject": subject,
        "goal": goal,
        "session_started_at": session_started_at.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "profile_reset": True,
        "activity_history_reset": True,
        "session_running": True,
        "personal_profile": reset_profile,
        "activity": None,
        "activity_history": []
    }


# =====================================================
# SAVE STUDY SESSION
# =====================================================

@app.post("/study-session")
def save_study_session(
    session: StudySession,
    authorization: str = Header(None)
):

    with study_session_save_lock:

        user = get_request_user(
            authorization,
            required=True
        )

        user_id = get_user_id(user)
        user_key = str(user_id)

        # If a rapid repeated request arrives just after the first save has
        # completed, return the same successful result instead of creating a
        # duplicate study-session record.
        recent_saved = recent_saved_session_by_user.get(user_key)
        if isinstance(recent_saved, dict):
            saved_at = float(recent_saved.get("saved_at", 0) or 0)
            if time.time() - saved_at <= RECENT_SAVED_SESSION_SECONDS:
                saved_subject = str(recent_saved.get("subject", "")).strip()
                saved_goal = str(recent_saved.get("goal", "")).strip()
                requested_subject = str(session.subject or "").strip()
                requested_goal = str(session.goal or "").strip()

                if (
                    saved_subject == requested_subject
                    and saved_goal == requested_goal
                ):
                    response = dict(recent_saved.get("response", {}))
                    response["message"] = "Study session was already saved"
                    response["duplicate_request"] = True
                    return response

        # A study-session record can only be saved for a currently running
        # study session.
        if not active_study_session_running_by_user.get(user_key, False):
            return {
                "status": "error",
                "message": "No active study session to save",
                "session_running": False
            }

        try:
            requested_duration = float(session.duration)
        except Exception:
            requested_duration = 0.0

        if requested_duration <= 0:
            requested_duration = 1.0

        active_session_number = active_study_session_number_by_user.get(
            user_key
        )

        if active_session_number is None:
            session_number = get_next_user_session_number(
                user_id
            )
        else:
            session_number = active_session_number

        # Recalculate the saved duration from actual recorded activity
        # boundaries.  The frontend value remains a fallback, but the backend
        # is the final authority so an outdated timer can no longer shorten
        # the stored session duration.
        duration = calculate_recorded_session_duration_for_user(
            user_id,
            session_number,
            requested_duration
        )

        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        saved_time = now.strftime("%H:%M:%S")

        csv_saved = append_user_study_session_to_csv(
            user_id,
            session_number,
            session.subject,
            session.goal,
            duration,
            date,
            saved_time
        )

        if not csv_saved:
            return {
                "status": "error",
                "message": "Study session could not be saved to user CSV"
            }

        mongodb_saved = save_study_session_to_mongodb(
            user_id,
            session_number,
            session.subject,
            session.goal,
            duration,
            date,
            saved_time
        )

        # STOP the live study session only after the session record has been
        # successfully written to CSV. The collector may continue running, but
        # subsequent /activity requests become live-only until Start Session is
        # pressed again.
        active_study_session_running_by_user[user_key] = False
        clear_active_study_session_state(
            user_id
        )

        # IMPORTANT: the completed session must disappear from the LIVE
        # Activity History / current-activity view immediately after End.
        # The saved session and its activities remain in CSV/MongoDB and can
        # still be opened from Study Session History. A new Start Session
        # creates a fresh session boundary and only its new activities appear
        # in the live history.
        latest_activity_by_user.pop(user_key, None)
        active_study_session_start_by_user.pop(user_key, None)
        active_study_session_number_by_user.pop(user_key, None)
        active_study_context_by_user.pop(user_key, None)

        previous_classification_by_user.pop(user_key, None)
        current_distraction_duration_by_user.pop(user_key, None)
        current_task_switches_by_user.pop(user_key, None)
        current_repeated_distractions_by_user.pop(user_key, None)
        last_distractive_end_by_user.pop(user_key, None)
        last_saved_activity_end_by_user.pop(user_key, None)
        ai_analysis_by_user.pop(user_key, None)

        response = {
            "status": "success",
            "message": "Study session saved successfully",
            "session": {
                "session_number": session_number,
                "subject": session.subject,
                "goal": session.goal,
                "duration": duration
            },
            "csv_file": get_user_study_sessions_file(user_id),
            "mongodb_saved": mongodb_saved,
            "session_running": False,
            "duplicate_request": False
        }

        recent_saved_session_by_user[user_key] = {
            "saved_at": time.time(),
            "subject": str(session.subject or "").strip(),
            "goal": str(session.goal or "").strip(),
            "session_number": session_number,
            "response": dict(response)
        }

        return response


# =====================================================
# SESSION DIAGNOSTICS
# =====================================================

@app.get("/study-session/{session_number}/summary")
def study_session_summary(
    session_number: str,
    authorization: str = Header(None)
):

    user = get_request_user(
        authorization,
        required=True
    )

    user_id = get_user_id(user)
    target = str(session_number).strip()
    activities = get_saved_session_activities(user_id, target)

    duration = calculate_recorded_session_duration_for_user(
        user_id,
        target,
        0
    )

    average_recovery = calculate_average_recovery_from_records(activities)

    return {
        "status": "success",
        "session_number": target,
        "activity_count": len(activities),
        "duration": duration,
        "average_recovery": round(average_recovery, 2),
        "activities": activities
    }


# =====================================================
# ACTIVE STUDY SESSION STATUS
# =====================================================

@app.get("/active-study-session")
def active_study_session_status(
    authorization: str = Header(None)
):
    user = get_request_user(
        authorization,
        required=True
    )

    user_id = get_user_id(user)

    restore_active_study_session_if_needed(
        user_id
    )

    user_key = str(user_id)

    running = bool(
        active_study_session_running_by_user.get(
            user_key,
            False
        )
    )

    session_number = active_study_session_number_by_user.get(
        user_key
    )

    start_time = active_study_session_start_by_user.get(
        user_key
    )

    context = active_study_context_by_user.get(
        user_key,
        {}
    )

    return {
        "status": "success",
        "session_running": running,
        "active_session": running,
        "session_number": session_number,
        "subject": (
            context.get("subject", "")
            if isinstance(context, dict)
            else ""
        ),
        "goal": (
            context.get("goal", "")
            if isinstance(context, dict)
            else ""
        ),
        "session_started_at": (
            start_time.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(start_time, datetime)
            else ""
        )
    }


# =====================================================
# GET STUDY SESSIONS
# =====================================================

@app.get("/study-sessions")
def get_study_sessions(
    authorization: str = Header(None)
):

    user = get_request_user(
        authorization,
        required=True
    )

    user_id = get_user_id(user)

    sessions = get_unified_study_session_history(
        user_id
    )

    return {
        "status": "success",
        "count": len(sessions),
        "sessions": sessions,
        "csv_file": get_user_study_sessions_file(user_id)
    }


# =====================================================
# GET STUDY SESSIONS FROM MONGODB
# =====================================================

@app.get("/mongodb-study-sessions")
def get_mongodb_study_sessions(
    authorization: str = Header(None)
):

    user = get_request_user(
        authorization,
        required=True
    )

    user_id = get_user_id(user)

    if not MONGODB_CONNECTED:
        return {
            "status": "error",
            "message": "MongoDB is not connected",
            "sessions": []
        }

    try:

        documents = list(
            study_sessions_collection.find(
                {
                    "user_id": str(user_id)
                },
                {
                    "_id": 0
                }
            ).sort(
                "created_at",
                -1
            )
        )

        sessions = []

        for item in documents:
            normalized = normalize_study_session_record(
                item
            )

            if normalized is not None:
                sessions.append(normalized)

        deduplicated = {}

        for item in sessions:
            deduplicated[
                item["session_number"]
            ] = item

        sessions = list(
            deduplicated.values()
        )

        sessions.sort(
            key=lambda item:
                int(item["session_number"])
                if str(item.get("session_number", "")).isdigit()
                else 0,
            reverse=True
        )

        return {
            "status": "success",
            "count": len(sessions),
            "sessions": sessions
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
            "sessions": []
        }


# =====================================================
# GET FULL ACTIVITY FOR A SAVED STUDY SESSION
# =====================================================

def get_saved_session_activities(user_id, session_number):

    """Return ONLY activities belonging to the requested saved session.

    CSV is preferred. MongoDB is also checked as a complement/fallback.
    Missing legacy start/end times are reconstructed from the stored
    timestamp (or created_at) and activity duration so older records also
    display real times.
    """

    target_session = str(session_number).strip()
    activities = []

    def parse_datetime(value):
        if isinstance(value, datetime):
            return value

        if value is None:
            return None

        text = str(value).strip()
        if not text:
            return None

        try:
            parsed = pd.to_datetime(text, errors="coerce")
            if pd.isna(parsed):
                return None
            return parsed.to_pydatetime()
        except Exception:
            return None

    def normalize_activity_times(item):
        """Fill missing Start Time / End Time from timestamp + duration."""
        normalized = dict(item)

        start_value = normalized.get("Start Time", normalized.get("start_time", ""))
        end_value = normalized.get("End Time", normalized.get("end_time", ""))

        start_dt = parse_datetime(start_value)
        end_dt = parse_datetime(end_value)

        duration_value = normalized.get(
            "Duration (seconds)",
            normalized.get("duration", 0)
        )

        try:
            duration = max(float(duration_value or 0), 0.0)
        except Exception:
            duration = 0.0

        # timestamp is the exact activity timestamp saved by the current
        # backend. created_at is retained as a fallback for older MongoDB rows.
        reference_dt = parse_datetime(
            normalized.get("timestamp", "")
        ) or parse_datetime(
            normalized.get("created_at", "")
        )

        if end_dt is None and reference_dt is not None:
            end_dt = reference_dt

        if end_dt is not None and start_dt is None:
            start_dt = datetime.fromtimestamp(
                end_dt.timestamp() - duration
            )

        if start_dt is not None and end_dt is None:
            end_dt = datetime.fromtimestamp(
                start_dt.timestamp() + duration
            )

        normalized["Start Time"] = (
            start_dt.strftime("%Y-%m-%d %H:%M:%S")
            if start_dt is not None
            else ""
        )

        normalized["End Time"] = (
            end_dt.strftime("%Y-%m-%d %H:%M:%S")
            if end_dt is not None
            else ""
        )

        return normalized

    # -------------------------------------------------
    # CSV
    # -------------------------------------------------
    try:
        for item in read_user_activity_records(user_id):
            item_session = str(
                item.get("Study Session", "") or
                item.get("study_session", "") or
                item.get("session_number", "") or
                ""
            ).strip()

            if item_session == target_session:
                activities.append(
                    normalize_activity_times(item)
                )
    except Exception as e:
        print("CSV study-session activity read error:", e)

    # -------------------------------------------------
    # MongoDB complement / fallback
    # -------------------------------------------------
    if MONGODB_CONNECTED:
        try:
            session_values = [target_session]
            if target_session.isdigit():
                session_values.append(int(target_session))

            mongo_items = list(
                activities_collection.find(
                    {
                        "user_id": str(user_id),
                        "$or": [
                            {"study_session": {"$in": session_values}},
                            {"session_number": {"$in": session_values}}
                        ]
                    },
                    {"_id": 0}
                )
            )

            def value(item, *keys):
                for key in keys:
                    if item.get(key) is not None:
                        return item.get(key)
                return ""

            def fingerprint(item):
                return (
                    str(value(item, "Application", "application") or "").strip(),
                    str(value(item, "Window", "window") or "").strip(),
                    str(value(item, "Start Time", "start_time") or "").strip(),
                    str(value(item, "End Time", "end_time") or "").strip(),
                    str(value(item, "Duration (seconds)", "duration") or "").strip(),
                    str(value(item, "Study Session", "study_session", "session_number") or "").strip()
                )

            existing = {fingerprint(item) for item in activities}

            for item in mongo_items:
                normalized = {
                    "Application": value(item, "Application", "application") or "Unknown",
                    "Window": value(item, "Window", "window") or "Unknown",
                    "Start Time": value(item, "Start Time", "start_time") or "",
                    "End Time": value(item, "End Time", "end_time") or "",
                    "Duration (seconds)": value(item, "Duration (seconds)", "duration") or 0,
                    "Classification": value(item, "Classification", "classification") or "Neutral",
                    "Recovery Time": value(item, "Recovery Time", "recovery_time") or 0,
                    "Task Switches": value(item, "Task Switches", "task_switches") or 0,
                    "Distraction Pattern": value(item, "Distraction Pattern", "distraction_pattern") or "",
                    "Distraction Evidence": value(item, "Distraction Evidence", "distraction_evidence") or "",
                    "Distraction Cost Score": value(item, "Distraction Cost Score", "distraction_cost_score") or "",
                    "Distraction Cost": value(item, "Distraction Cost", "distraction_cost") or "",
                    "Study Session": str(value(item, "Study Session", "study_session", "session_number") or target_session),
                    "Study Subject": value(item, "Study Subject", "study_subject", "subject") or "",
                    "Study Goal": value(item, "Study Goal", "study_goal", "goal") or "",
                    "timestamp": value(item, "timestamp"),
                    "created_at": value(item, "created_at")
                }

                normalized = normalize_activity_times(normalized)

                if str(normalized["Study Session"]).strip() != target_session:
                    continue

                fp = fingerprint(normalized)
                if fp not in existing:
                    activities.append(normalized)
                    existing.add(fp)

        except Exception as e:
            print("MongoDB study-session activity read error:", e)

    # -------------------------------------------------
    # Strict final session filter
    # -------------------------------------------------
    filtered = []
    for item in activities:
        normalized = normalize_activity_times(item)

        item_session = str(
            normalized.get("Study Session", "") or
            normalized.get("study_session", "") or
            normalized.get("session_number", "") or
            ""
        ).strip()

        if item_session == target_session:
            filtered.append(normalized)

    # Prefer timestamped records when an older blank-time CSV copy and a
    # richer MongoDB copy refer to the same activity.
    def loose_activity_key(item):
        return (
            str(item.get("Application", item.get("application", "")) or "").strip(),
            str(item.get("Window", item.get("window", "")) or "").strip(),
            str(item.get("Duration (seconds)", item.get("duration", 0)) or "").strip(),
            str(item.get("Study Session", item.get("study_session", "")) or "").strip()
        )

    keys_with_times = set()
    for item in filtered:
        if (
            str(item.get("Start Time", "") or "").strip() and
            str(item.get("End Time", "") or "").strip()
        ):
            keys_with_times.add(loose_activity_key(item))

    cleaned = []
    seen_fingerprints = set()

    for item in filtered:
        start_value = str(item.get("Start Time", "") or "").strip()
        end_value = str(item.get("End Time", "") or "").strip()
        key = loose_activity_key(item)

        # Drop a blank legacy CSV copy when a timestamped copy exists.
        if not start_value and not end_value and key in keys_with_times:
            continue

        fingerprint = (key, start_value, end_value)
        if fingerprint not in seen_fingerprints:
            cleaned.append(item)
            seen_fingerprints.add(fingerprint)

    def parse_session_time(item):
        value = item.get("Start Time", item.get("start_time", "")) or ""
        parsed = parse_datetime(value)
        return parsed or datetime.max

    cleaned.sort(key=parse_session_time)
    return cleaned


@app.get(
    "/study-session/{session_number}/activities",
    dependencies=[Depends(swagger_bearer)]
)
def study_session_activities(
    session_number: str,
    authorization: str = Header(None)
):

    user = get_request_user(
        authorization,
        required=True
    )

    user_id = get_user_id(user)
    target_session = str(session_number).strip()

    if not target_session:
        return {
            "status": "error",
            "message": "Session number is required",
            "activities": []
        }

    try:

        activities = get_saved_session_activities(
            user_id,
            target_session
        )

        # Find the saved session metadata from the unified CSV + MongoDB
        # history so View Activity works even if one store is missing.
        sessions = get_unified_study_session_history(
            user_id
        )
        selected_session = None

        for session in sessions:
            if str(session.get("session_number", "")).strip() == target_session:
                selected_session = session
                break

        # Build a summary directly from the stored activity records.
        productive_time = 0.0
        distractive_time = 0.0
        neutral_time = 0.0
        total_distractions = 0
        total_task_switches = 0

        for item in activities:

            classification = str(
                item.get("Classification", "Neutral") or "Neutral"
            ).strip().lower()

            try:
                duration = float(
                    item.get("Duration (seconds)", 0) or 0
                )
            except Exception:
                duration = 0.0

            if classification == "productive":
                productive_time += duration
            elif classification == "distractive":
                distractive_time += duration
                total_distractions += 1
            else:
                neutral_time += duration

            try:
                total_task_switches += int(
                    float(item.get("Task Switches", 0) or 0)
                )
            except Exception:
                pass

        return {
            "status": "success",
            "session_number": target_session,
            "session": selected_session,
            "activity_count": len(activities),
            "activities": activities,
            "summary": {
                "productive_time": round(productive_time, 2),
                "distractive_time": round(distractive_time, 2),
                "neutral_time": round(neutral_time, 2),
                "total_tracked_time": round(
                    productive_time + distractive_time + neutral_time,
                    2
                ),
                "total_distractions": total_distractions,
                "task_switches": total_task_switches
            }
        }

    except Exception as e:

        print(
            "Study session activity history error:",
            e
        )

        return {
            "status": "error",
            "message": str(e),
            "session_number": target_session,
            "session": None,
            "activity_count": 0,
            "activities": [],
            "summary": {
                "productive_time": 0,
                "distractive_time": 0,
                "neutral_time": 0,
                "total_tracked_time": 0,
                "total_distractions": 0,
                "task_switches": 0
            }
        }


# =====================================================
# DELETE STUDY SESSIONS
# =====================================================

@app.delete("/study-sessions")
def clear_study_sessions(
    authorization: str = Header(None)
):

    user = get_request_user(
        authorization,
        required=True
    )

    user_id = get_user_id(user)

    _, sessions_file = prepare_user_data(
        user_id
    )

    try:

        if os.path.exists(sessions_file):
            os.remove(sessions_file)

        # Clearing history must also remove any persisted active-session
        # marker so an old session cannot reappear after a FastAPI restart.
        clear_active_study_session_state(
            user_id
        )

        active_study_session_start_by_user.pop(
            str(user_id),
            None
        )
        active_study_session_number_by_user.pop(
            str(user_id),
            None
        )
        active_study_session_running_by_user.pop(
            str(user_id),
            None
        )
        active_study_context_by_user.pop(
            str(user_id),
            None
        )

        if MONGODB_CONNECTED:
            study_sessions_collection.delete_many(
                {
                    "user_id": str(user_id)
                }
            )

        print(
            "Study sessions cleared for user:",
            user_id
        )

        return {
            "status": "success",
            "message": "Study session history cleared"
        }

    except Exception as e:

        print(
            "Study session delete error:",
            e
        )

        return {
            "status": "error",
            "message": str(e)
        }


# =====================================================
# PROFILE
# =====================================================

@app.get("/profile")
def profile(
    authorization: str = Header(None)
):

    user = get_request_user(
        authorization,
        required=True
    )

    user_id = get_user_id(user)

    current_profile = build_user_profile(
        user_id
    )

    if MONGODB_CONNECTED:
        save_profile_to_mongodb(
            user_id,
            current_profile
        )

    return {
        "status": "success",
        "personal_profile": current_profile
    }


# =====================================================
# LATEST ACTIVITY
# =====================================================

@app.get("/latest-activity")
def get_latest_activity(
    authorization: str = Header(None)
):

    user = get_request_user(
        authorization,
        required=True
    )

    user_id = get_user_id(user)

    latest = latest_activity_by_user.get(
        str(user_id)
    )

    if latest is not None:

        return {
            "status": "success",
            "activity": latest
        }

    activities = read_user_activity_records(
        user_id
    )

    activities = filter_activities_for_current_study_session(
        user_id,
        activities
    )

    if activities:

        latest = activities[0]

        return {
            "status": "success",
            "activity": {
                "application": latest.get("Application", ""),
                "window": latest.get("Window", ""),
                "duration": latest.get("Duration (seconds)", 0),
                "classification": latest.get("Classification", "Neutral")
            },
            "study_context": get_current_study_context(user_id)
        }

    return {
        "status": "success",
        "activity": None,
        "study_context": get_current_study_context(user_id)
    }


# =====================================================
# ACTIVITY HISTORY
# =====================================================

@app.get("/activity-history")
def activity_history(
    authorization: str = Header(None),
    all: bool = False
):

    user = get_request_user(
        authorization,
        required=True
    )

    user_id = get_user_id(user)

    activities = read_user_activity_records(
        user_id
    )

    # Default behavior remains the live/current-study-session history.
    # Study Session History can request all saved activities explicitly.
    if not all:
        activities = filter_activities_for_current_study_session(
            user_id,
            activities
        )

    return {
        "status": "success",
        "count": len(activities),
        "activities": activities,
        "study_context": get_current_study_context(user_id),
        "all": bool(all)
    }


# =====================================================
# MONGODB ACTIVITY HISTORY
# =====================================================

@app.get("/mongodb-activity-history")
def mongodb_activity_history(
    authorization: str = Header(None)
):

    user = get_request_user(
        authorization,
        required=True
    )

    user_id = get_user_id(user)

    if not MONGODB_CONNECTED:
        return {
            "status": "error",
            "message": "MongoDB is not connected",
            "count": 0,
            "activities": []
        }

    try:

        query = {
            "user_id": str(user_id)
        }

        session_start = get_current_study_session_start(
            user_id
        )

        if session_start is not None:
            query["created_at"] = {
                "$gte": session_start
            }

        activities = list(
            activities_collection.find(
                query,
                {
                    "_id": 0
                }
            ).sort(
                "created_at",
                -1
            )
        )

        return {
            "status": "success",
            "count": len(activities),
            "activities": activities,
            "study_context": get_current_study_context(user_id)
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
            "count": 0,
            "activities": []
        }


# =====================================================
# CLEAR ACTIVITY HISTORY
# =====================================================

@app.delete("/activity-history")
def clear_activity_history(
    authorization: str = Header(None)
):

    global previous_classification_by_user
    global current_distraction_duration_by_user
    global current_task_switches_by_user
    global current_repeated_distractions_by_user

    user = get_request_user(
        authorization,
        required=True
    )

    user_id = get_user_id(user)

    activity_file, _ = prepare_user_data(
        user_id
    )

    try:

        if os.path.exists(activity_file):
            os.remove(activity_file)

        if MONGODB_CONNECTED:
            activities_collection.delete_many(
                {
                    "user_id": str(user_id)
                }
            )

        latest_activity_by_user.pop(
            str(user_id),
            None
        )

        previous_classification_by_user.pop(
            str(user_id),
            None
        )

        current_distraction_duration_by_user.pop(
            str(user_id),
            None
        )

        current_task_switches_by_user.pop(
            str(user_id),
            None
        )

        current_repeated_distractions_by_user.pop(
            str(user_id),
            None
        )

        recent_activities_by_user.pop(
            str(user_id),
            None
        )

        ai_analysis_by_user.pop(
            str(user_id),
            None
        )

        active_study_session_start_by_user.pop(
            str(user_id),
            None
        )

        active_study_session_number_by_user.pop(
            str(user_id),
            None
        )
        active_study_session_running_by_user.pop(
            str(user_id),
            None
        )
        last_saved_activity_end_by_user.pop(
            str(user_id),
            None
        )
        last_distractive_end_by_user.pop(
            str(user_id),
            None
        )
        recent_saved_session_by_user.pop(
            str(user_id),
            None
        )

        # Clear only this user's cached classifications.
        clear_ai_cache_for_user(
            user_id
        )

        print(
            "Activity history cleared for user:",
            user_id
        )

        return {
            "status": "success",
            "message": "Activity history cleared"
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }


# =====================================================
# ACTIVITY
# =====================================================

@app.post("/activity")
def receive_activity(
    activity: Activity,
    authorization: str = Header(None)
):

    # Reconnect if MongoDB was started after FastAPI.
    ensure_mongodb_connection()

    # The desktop collector can keep an older valid token on disk. Because
    # that token can belong to a previous FocusSense user without producing
    # a 401, prefer the most recently authenticated local user whenever the
    # supplied collector token does not match that user's current token.
    #
    # Browser/API requests that use the current token continue normally.
    global active_user

    supplied_token = ""
    if (
        authorization and
        authorization.startswith("Bearer ")
    ):
        supplied_token = authorization.replace(
            "Bearer ",
            "",
            1
        ).strip()

    if (
        active_user is not None and
        supplied_token and
        supplied_token != str(active_user.get("token", "")).strip()
    ):
        user = active_user
    else:
        user = get_request_user(
            authorization,
            required=True,
            allow_active=True
        )

    user_id = get_user_id(user)
    user_key = str(user_id)

    # Recover the active session if FastAPI was restarted after the user
    # pressed Start Study Session.
    restore_active_study_session_if_needed(
        user_id
    )

    # Capture the session number at the exact moment this activity request
    # begins. If the user presses Stop or starts another session while Groq
    # is still processing this request, the final persistence check below
    # will reject the stale activity instead of attaching it to the wrong
    # study session.
    request_session_number = active_study_session_number_by_user.get(
        user_key
    )

    # Capture activity timestamps before the Groq request so AI/network
    # latency cannot shift the saved interval. Prefer exact collector values;
    # older collectors can omit them and the backend reconstructs the interval
    # from request time + duration.
    try:
        activity_duration_seconds = max(float(activity.duration or 0), 0.0)
    except Exception:
        activity_duration_seconds = 0.0

    exact_start = parse_activity_datetime(activity.start_time)
    exact_end = parse_activity_datetime(activity.end_time or activity.timestamp)

    if exact_end is None:
        exact_end = datetime.now()
    if exact_start is None:
        exact_start = datetime.fromtimestamp(
            exact_end.timestamp() - activity_duration_seconds
        )

    # Activity intervals should be sequential.  If an older collector rounds
    # or reports the next start slightly before the previous saved end, align
    # the boundary when the discrepancy is <= 1.5 seconds.  Duration itself is
    # preserved.
    previous_end = last_saved_activity_end_by_user.get(user_key)
    if isinstance(previous_end, datetime):
        overlap_seconds = previous_end.timestamp() - exact_start.timestamp()
        if 0 < overlap_seconds <= 1.5:
            exact_start = previous_end
            exact_end = datetime.fromtimestamp(
                exact_start.timestamp() + activity_duration_seconds
            )

    activity_end_datetime = exact_end
    activity_start_datetime = exact_start

    # The collector can continue running after Stop. Normally, an activity
    # arriving outside an active session is live-only.
    #
    # IMPORTANT FIX:
    # A collector request can already be in flight at exactly the moment the
    # user clicks Start Study Session. The old code captured None here and
    # immediately returned LIVE ONLY, so the first activity after starting a
    # session could be lost. Re-check the shared session state for a short
    # grace window before deciding. If the session started during that
    # window, attach the current activity to the new session.
    if (
        not active_study_session_running_by_user.get(user_key, False)
        or request_session_number is None
    ):
        grace_deadline = time.time() + SESSION_START_GRACE_SECONDS

        while time.time() < grace_deadline:
            current_session_number = active_study_session_number_by_user.get(
                user_key
            )
            current_session_running = active_study_session_running_by_user.get(
                user_key,
                False
            )

            if current_session_running and current_session_number is not None:
                session_started_at = active_study_session_start_by_user.get(
                    user_key
                )

                # Only recover the request when the activity ended at or after
                # the new session started. If the entire activity happened
                # before Start was clicked, it remains live-only.
                if (
                    isinstance(session_started_at, datetime)
                    and activity_end_datetime >= session_started_at
                ):
                    request_session_number = current_session_number

                    # If the collector interval began before the session
                    # started, record only the portion that actually occurred
                    # during the study session.
                    if activity_start_datetime < session_started_at:
                        activity_start_datetime = session_started_at
                        activity_duration_seconds = max(
                            (
                                activity_end_datetime
                                - activity_start_datetime
                            ).total_seconds(),
                            0.0
                        )
                        activity.duration = round(
                            activity_duration_seconds,
                            2
                        )

                    print(
                        "SESSION START GRACE - activity attached to new study session"
                    )
                    break

            time.sleep(0.05)
        else:
            # No session became active during the grace window. Keep the
            # original live-only behavior.
            live_activity = {
                "application": activity.application,
                "start_time": activity_start_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": activity_end_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                "study_session": None,
                "study_subject": "",
                "study_goal": "",
                "window": activity.window,
                "duration": activity.duration,
                "classification": "Neutral",
                "distraction": {
                    "is_distraction": False,
                    "pattern": "No active study session",
                    "evidence": "Activity is shown live but is not recorded."
                },
                "recovery": {
                    "recovery_started": False,
                    "recovery_completed": False,
                    "recovery_time": 0
                },
                "distraction_cost": None,
                "ai_confidence": 0.0,
                "ai_reason": "No active study session. Activity is shown live but is not recorded.",
                "ai_pattern": "",
                "ai_evidence": "Activity is shown live but is not recorded.",
                "timestamp": activity_end_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                "recorded": False,
                "live_only": True
            }

            latest_activity_by_user[user_key] = live_activity

            print("LIVE ONLY - Activity shown but NOT saved")
            return {
                "status": "success",
                "message": "Activity shown live only because no study session is active.",
                "recorded": False,
                "live_only": True,
                "activity": {
                    "application": activity.application,
                    "window": activity.window,
                    "duration": activity.duration,
                    "classification": "Neutral",
                    "ai_confidence": 0.0,
                    "ai_reason": live_activity["ai_reason"],
                    "start_time": live_activity["start_time"],
                    "end_time": live_activity["end_time"],
                    "study_session": "",
                    "study_subject": "",
                    "study_goal": ""
                },
                "ai_classification": {
                    "classification": "Neutral",
                    "confidence": 0.0,
                    "reason": live_activity["ai_reason"],
                    "pattern": "",
                    "evidence": live_activity["ai_evidence"]
                },
                "distraction_analysis": live_activity["distraction"],
                "recovery_analysis": live_activity["recovery"],
                "distraction_cost": None,
                "personal_profile": None,
                "study_context": {},
                "csv_saved": False,
                "mongodb_activity_saved": False,
                "mongodb_profile_saved": False,
                "user": {
                    "username": user.get("username", ""),
                    "email": user.get("email", "")
                }
            }

    previous_classification = (
        previous_classification_by_user.get(
            user_key
        )
    )

    current_distraction_duration = (
        current_distraction_duration_by_user.get(
            user_key,
            0.0
        )
    )

    current_task_switches = (
        current_task_switches_by_user.get(
            user_key,
            0
        )
    )

    current_repeated_distractions = (
        current_repeated_distractions_by_user.get(
            user_key,
            0
        )
    )

    # =================================================
    # 1. CLASSIFICATION
    # =================================================

    # =================================================
    # 1. AI CLASSIFICATION
    # =================================================

    classification = get_classification(
        activity.application,
        activity.window,
        activity.duration,
        user_id
    )

    ai_result = ai_analysis_by_user.get(
        user_key,
        {
            "classification": classification,
            "confidence": 0.0,
            "reason": "",
            "pattern": "",
            "evidence": activity.window
        }
    )

    if not isinstance(ai_result, dict):
        ai_result = {
            "classification": classification,
            "confidence": 0.0,
            "reason": "AI returned no usable classification.",
            "pattern": "AI response error",
            "evidence": activity.window
        }

    study_context = get_current_study_context(user_id)
    if not isinstance(study_context, dict):
        study_context = {}
    study_subject = study_context.get("subject", "")
    study_goal = study_context.get("goal", "")
    study_session_number = study_context.get("session_number", "")

    # Keep a short recent sequence for future AI classifications.
    recent_list = recent_activities_by_user.get(
        user_key,
        []
    )

    recent_list.append({
        "application": activity.application,
        "window": activity.window,
        "classification": classification
    })

    recent_activities_by_user[
        user_key
    ] = recent_list[-5:]

    # The AI call can take several seconds. The user may have pressed Stop
    # or started a new session while Groq was processing. Never save an
    # activity that belongs to an old/stopped session.
    if (
        not active_study_session_running_by_user.get(user_key, False)
        or active_study_session_number_by_user.get(user_key)
        != request_session_number
    ):
        print("Activity ignored - study session stopped or changed during AI processing")
        return {
            "status": "ignored",
            "message": "Activity was not recorded because the study session stopped or changed.",
            "recorded": False,
            "activity": None,
            "study_context": get_current_study_context(user_id)
        }

    # =================================================
    # 2. PROCESS ACTIVITY
    # =================================================

    result = {
        "application": activity.application,
        "window": activity.window,
        "duration": activity.duration,
        "classification": classification,
        "ai_confidence": ai_result.get("confidence", 0.0),
        "ai_reason": ai_result.get("reason", ""),
        "recorded": True,
        "live_only": False
    }

    # =================================================
    # 3. DISTRACTION ANALYSIS
    # =================================================

    try:

        distraction = analyze_distraction(
            activity.application,
            activity.window,
            activity.duration,
            classification
        )

        if not isinstance(distraction, dict):
            distraction = None

    except Exception as e:

        print(
            "Distraction engine error:",
            e
        )

        distraction = {
            "is_distraction": classification == "Distractive",
            "pattern": (
                "Known distracting activity"
                if classification == "Distractive"
                else "None"
            ),
            "evidence": activity.window
        }

    if not isinstance(distraction, dict):
        distraction = {
            "is_distraction": classification == "Distractive",
            "pattern": (
                "Known distracting activity"
                if classification == "Distractive"
                else "None"
            ),
            "evidence": activity.window
        }

    # Add the AI explanation without replacing the existing distraction engine.
    distraction["ai_confidence"] = ai_result.get(
        "confidence",
        0.0
    )

    distraction["ai_reason"] = ai_result.get(
        "reason",
        ""
    )

    if ai_result.get("pattern"):

        distraction["ai_pattern"] = ai_result.get(
            "pattern",
            ""
        )

    if ai_result.get("evidence"):

        distraction["ai_evidence"] = ai_result.get(
            "evidence",
            ""
        )

    # =================================================
    # 4. EXACT RECOVERY FOR RECORDED ACTIVITY
    # =================================================

    # Recovery must use the collector's exact activity boundaries. Using
    # datetime.now() or the time after Groq returns would incorrectly count
    # AI/network latency as student recovery time.
    recovery = {
        "recovery_started": False,
        "recovery_completed": False,
        "recovery_time": 0.0
    }

    last_distractive_end = last_distractive_end_by_user.get(
        user_key
    )

    if classification == "Productive" and isinstance(
        last_distractive_end,
        datetime
    ):
        recovery_seconds = (
            activity_start_datetime.timestamp()
            - last_distractive_end.timestamp()
        )

        if 0 <= recovery_seconds <= 3600:
            recovery = {
                "recovery_started": True,
                "recovery_completed": True,
                "recovery_time": round(
                    recovery_seconds,
                    2
                )
            }

    # =================================================
    # 5. TRACK DISTRACTION
    # =================================================

    new_task_switches = 0
    pending_distractive_end = None
    clear_distractive_recovery_state = False

    if classification == "Distractive":

        current_distraction_duration += float(
            activity.duration
        )

        pending_distractive_end = activity_end_datetime

        if previous_classification is not None:

            if previous_classification != classification:

                current_task_switches += 1
                new_task_switches = 1

        if (
            distraction.get("pattern") ==
            "Repeated social-media checking"
        ):

            current_repeated_distractions += 1

    if classification == "Productive" and recovery.get(
        "recovery_completed",
        False
    ):
        clear_distractive_recovery_state = True

    # =================================================
    # 6. DISTRACTION COST
    # =================================================

    distraction_cost = None

    if recovery.get(
        "recovery_completed",
        False
    ):

        try:

            distraction_cost = calculate_distraction_cost(
                current_distraction_duration,
                recovery.get(
                    "recovery_time",
                    0
                ),
                current_task_switches,
                current_repeated_distractions
            )

        except Exception as e:

            print(
                "Distraction cost error:",
                e
            )

    # =================================================
    # 7. USER PROFILE
    # =================================================

    current_context = active_study_context_by_user.get(
        user_key,
        {}
    )

    if not isinstance(current_context, dict):
        current_context = {}

    latest_activity = {
        "application": activity.application,
        "start_time": activity_start_datetime.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "end_time": activity_end_datetime.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "window": activity.window,
        "duration": activity.duration,
        "classification": classification,
        "distraction": distraction,
        "recovery": recovery,
        "distraction_cost": distraction_cost,
        "ai_confidence": ai_result.get("confidence", 0.0),
        "ai_reason": ai_result.get("reason", ""),
        "ai_pattern": ai_result.get("pattern", ""),
        "ai_evidence": ai_result.get("evidence", ""),
        "recorded": True,
        "live_only": False,
        "study_session": study_session_number,
        "study_subject": study_subject,
        "study_goal": study_goal,
        "timestamp": activity_end_datetime.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    }

    # =================================================
    # 8. FINAL SESSION CHECK BEFORE PERSISTENCE
    # =================================================

    # Stop/start can happen while the activity is being processed. Check one
    # more time immediately before writing anything to disk or MongoDB.
    if (
        not active_study_session_running_by_user.get(user_key, False)
        or active_study_session_number_by_user.get(user_key)
        != request_session_number
    ):
        print("Activity ignored - session changed before persistence")
        return {
            "status": "ignored",
            "message": "Activity was not recorded because the study session stopped or changed before saving.",
            "recorded": False,
            "activity": None,
            "study_context": get_current_study_context(user_id)
        }

    # =================================================
    # 8. SAVE ACTIVITY CSV
    # =================================================

    csv_saved = append_user_activity_to_csv(
        user_id,
        latest_activity,
        recovery.get(
            "recovery_time",
            0
        ),
        new_task_switches
    )

    # =================================================
    # 9. SAVE ACTIVITY TO MONGODB
    # =================================================

    mongodb_activity = {
        "application": activity.application,
        "start_time": latest_activity["start_time"],
        "end_time": latest_activity["end_time"],
        "study_session": request_session_number,
        "study_subject": current_context.get("subject", ""),
        "study_goal": current_context.get("goal", ""),
        "window": activity.window,
        "duration": activity.duration,
        "classification": classification,
        "distraction": distraction,
        "recovery": recovery,
        "distraction_cost": distraction_cost,
        "task_switches": new_task_switches,
        "ai_confidence": ai_result.get("confidence", 0.0),
        "ai_reason": ai_result.get("reason", ""),
        "ai_pattern": ai_result.get("pattern", ""),
        "ai_evidence": ai_result.get("evidence", ""),
        "study_session": study_session_number,
        "study_subject": study_subject,
        "study_goal": study_goal,
        "timestamp": latest_activity["timestamp"]
    }

    mongodb_activity_saved = save_activity_to_mongodb(
        user_id,
        mongodb_activity
    )

    # Remember the exact persisted boundary so the next event can be aligned
    # if a legacy collector produces a tiny timestamp overlap.
    if csv_saved or mongodb_activity_saved:
        last_saved_activity_end_by_user[user_key] = activity_end_datetime

        if pending_distractive_end is not None:
            last_distractive_end_by_user[user_key] = pending_distractive_end
        elif clear_distractive_recovery_state:
            last_distractive_end_by_user.pop(
                user_key,
                None
            )

    # =================================================
    # 10. UPDATE USER PROFILE
    # =================================================

    profile = build_user_profile(
        user_id
    )

    if not isinstance(profile, dict):
        profile = {
            "productive_time": 0.0,
            "distractive_time": 0.0,
            "productive_percentage": 0.0,
            "total_distractions": 0,
            "average_recovery_time": 0.0,
            "task_switches": 0,
            "common_distraction": "None",
            "sessions": 0
        }

    mongodb_profile_saved = save_profile_to_mongodb(
        user_id,
        profile
    )

    # =================================================
    # 11. SAVE USER STATE
    # =================================================

    previous_classification_by_user[
        user_key
    ] = classification

    current_distraction_duration_by_user[
        user_key
    ] = current_distraction_duration

    current_task_switches_by_user[
        user_key
    ] = current_task_switches

    current_repeated_distractions_by_user[
        user_key
    ] = current_repeated_distractions

    latest_activity_by_user[
        user_key
    ] = latest_activity

    # =================================================
    # 12. TERMINAL OUTPUT
    # =================================================

    print("--------------------------------")
    print("Activity received")
    print("User        :", user.get("username", ""))
    print("Application :", activity.application)
    print("Window      :", activity.window)
    print("Duration    :", activity.duration, "seconds")
    print("Classification:", classification)
    print(
        "AI Confidence:",
        ai_result.get("confidence", 0.0)
    )
    print(
        "AI Reason:",
        ai_result.get("reason", "")
    )
    print(
        "AI Pattern:",
        ai_result.get("pattern", "")
    )

    if classification == "Distractive":
        print("DISTRACTION DETECTED")
        print(
            "Possible Pattern:",
            distraction.get(
                "pattern",
                "Known distracting activity"
            )
        )
        print(
            "Evidence:",
            distraction.get(
                "evidence",
                activity.window
            )
        )
    else:
        print("Distraction: No")

    if recovery.get("recovery_started", False):
        print("Recovery tracking started")

    if recovery.get("recovery_completed", False):
        print("Recovery completed")
        print(
            "Recovery Time:",
            recovery.get("recovery_time", 0),
            "seconds"
        )

    if distraction_cost is not None:
        print("DISTRACTION COST")
        print(
            "Cost Score:",
            distraction_cost.get("score", 0)
        )
        print(
            "Cost Level:",
            distraction_cost.get("cost", "Unknown")
        )

    print("PERSONAL PROFILE")
    print(
        "Productive Time:",
        profile.get("productive_time", 0),
        "seconds"
    )
    print(
        "Distractive Time:",
        profile.get("distractive_time", 0),
        "seconds"
    )
    print(
        "Productive Percentage:",
        profile.get("productive_percentage", 0),
        "%"
    )
    print(
        "Total Distractions:",
        profile.get("total_distractions", 0)
    )
    print(
        "Average Recovery:",
        profile.get("average_recovery_time", 0),
        "seconds"
    )
    print(
        "Common Distraction:",
        profile.get("common_distraction", "None")
    )
    print(
        "Task Switches:",
        profile.get("task_switches", 0)
    )
    print(
        "CSV:",
        "Saved" if csv_saved else "Not Saved"
    )
    print(
        "MongoDB:",
        "SAVED ✓" if mongodb_activity_saved else "NOT SAVED ✗"
    )

    if csv_saved and mongodb_activity_saved:
        print("✓ ACTIVITY RECORDED SUCCESSFULLY")
        print("✓ Saved to CSV")
        print("✓ Saved to MongoDB (activities)")
    elif not mongodb_activity_saved:
        print("✗ ACTIVITY RECORDING INCOMPLETE - MongoDB save failed")
    elif not csv_saved:
        print("✗ ACTIVITY RECORDING INCOMPLETE - CSV save failed")

    print("--------------------------------")

    # =================================================
    # 13. RESPONSE
    # =================================================

    return {
        "status": "success",
        "message": "Activity processed successfully",
        "activity": result,
        "ai_classification": ai_result,
        "distraction_analysis": distraction,
        "recovery_analysis": recovery,
        "distraction_cost": distraction_cost,
        "personal_profile": profile,
        "study_context": study_context,
        "mongodb": (
            "saved"
            if mongodb_activity_saved
            else "not saved"
        ),
        "csv_saved": csv_saved,
        "mongodb_activity_saved": mongodb_activity_saved,
        "mongodb_profile_saved": mongodb_profile_saved,
        "recorded": bool(csv_saved and mongodb_activity_saved),
        "live_only": False,
        "active_session": True,
        "session_running": True,
        "session_number": request_session_number,
        "user": {
            "username": user.get("username", ""),
            "email": user.get("email", "")
        }
    }
