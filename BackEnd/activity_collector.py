import os
import sys
import time
import threading
from queue import Queue
from datetime import datetime

import psutil
import requests
import win32gui
import win32process


# =====================================================
# FOCUSSENSE ACTIVITY COLLECTOR
# =====================================================
# RESPONSIBILITIES OF THIS COLLECTOR:
#   1. Detect the active Windows application/window.
#   2. Measure activity start/end timestamps.
#   3. Send activity to FastAPI.
#
# FASTAPI IS THE SINGLE SOURCE OF TRUTH FOR:
#   - AI classification
#   - study-session context
#   - CSV persistence
#   - MongoDB persistence
#   - recovery/distraction analysis
#   - live-only behavior
#
# IMPORTANT LIVE-ONLY RULE:
# If FastAPI says the activity is LIVE ONLY, this collector
# deliberately displays it as Neutral and does NOT display
# stale AI context from a previous study session.
# =====================================================


# =====================================================
# CONFIGURATION
# =====================================================

# Keep packaged and source runs on the same writable data directory.
# This prevents a frozen collector from accidentally looking for the login
# token inside PyInstaller's read-only _internal folder.
DATA_DIR = os.environ.get("FOCUSSENSE_DATA_DIR", "").strip()

if not DATA_DIR and getattr(sys, "frozen", False):
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        DATA_DIR = os.path.join(local_app_data, "FocusSense", "data")

if not DATA_DIR:
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))

os.makedirs(DATA_DIR, exist_ok=True)

TOKEN_FILE = os.path.join(DATA_DIR, "collector_token.txt")

API_URL = os.environ.get(
    "FOCUSSENSE_API_URL",
    "http://127.0.0.1:8000"
).strip().rstrip("/")

ACTIVITY_ENDPOINT = f"{API_URL}/activity"

API_TIMEOUT = float(
    os.environ.get("FOCUSSENSE_COLLECTOR_TIMEOUT", "15")
)

POLL_INTERVAL = float(
    os.environ.get("FOCUSSENSE_POLL_INTERVAL", "1.0")
)

MIN_ACTIVITY_DURATION = float(
    os.environ.get("FOCUSSENSE_MIN_ACTIVITY_DURATION", "0.0")
)

# Number of immediate retries for temporary FastAPI connection errors.
MAX_REQUEST_RETRIES = int(
    os.environ.get("FOCUSSENSE_COLLECTOR_RETRIES", "2")
)

RETRY_DELAY = float(
    os.environ.get("FOCUSSENSE_COLLECTOR_RETRY_DELAY", "1.0")
)


# =====================================================
# REQUEST SESSION
# =====================================================

http_session = requests.Session()


# =====================================================
# COLLECTOR TOKEN
# =====================================================

def get_collector_token():
    """Read the bearer token created by FocusSense login."""

    if not os.path.exists(TOKEN_FILE):
        return ""

    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as file:
            return file.read().strip()
    except Exception as error:
        print("Collector token read error:", error)
        return ""


def build_headers():
    """Build headers used for every FastAPI activity request."""

    headers = {
        "Content-Type": "application/json"
    }

    token = get_collector_token()

    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


# =====================================================
# ACTIVE WINDOW INFORMATION
# =====================================================

def get_active_window_info():
    """Return (process_name, foreground_window_title)."""

    try:
        hwnd = win32gui.GetForegroundWindow()
        window_title = win32gui.GetWindowText(hwnd)

        _, pid = win32process.GetWindowThreadProcessId(hwnd)

        if not pid:
            return "Unknown", window_title

        process = psutil.Process(pid)
        application = process.name()

        return application, window_title

    except Exception as error:
        print("Active window detection error:", error)
        return "Unknown", ""


# =====================================================
# DATE/TIME DISPLAY
# =====================================================

def format_local_datetime(timestamp):
    """Format Unix timestamp for terminal output."""

    try:
        return datetime.fromtimestamp(float(timestamp)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except Exception:
        return "Unknown"


# =====================================================
# DEFAULT RESULT
# =====================================================

def failed_result(reason):
    """Return a safe result when FastAPI cannot confirm activity."""

    return {
        "success": False,
        "classification": "Neutral",
        "confidence": 0.0,
        "reason": reason,
        "pattern": "",
        "evidence": "",
        "recorded": False,
        "live_only": False,
        "active_session": False,
    }


# =====================================================
# SEND ACTIVITY TO FASTAPI
# =====================================================

def send_activity_to_fastapi(
    application,
    window_title,
    duration,
    start_timestamp,
    end_timestamp
):
    """Send one activity with exact collector timestamps to FastAPI."""

    safe_duration = max(float(duration), 0.0)
    safe_start = float(start_timestamp)
    safe_end = float(end_timestamp)

    payload = {
        "application": str(application),
        "window": str(window_title),
        "duration": round(safe_duration, 2),
        "start_time": safe_start,
        "end_time": safe_end,
        "timestamp": safe_end,
    }

    response = None

    # -------------------------------------------------
    # REQUEST + SMALL RETRY FOR TEMPORARY CONNECTION ERRORS
    # -------------------------------------------------

    for attempt in range(MAX_REQUEST_RETRIES + 1):
        try:
            response = http_session.post(
                ACTIVITY_ENDPOINT,
                json=payload,
                headers=build_headers(),
                timeout=API_TIMEOUT,
            )
            break

        except requests.exceptions.ConnectionError:
            if attempt < MAX_REQUEST_RETRIES:
                print(
                    f"FastAPI connection unavailable. "
                    f"Retrying ({attempt + 1}/{MAX_REQUEST_RETRIES})..."
                )
                time.sleep(RETRY_DELAY)
                continue

            print("Could not connect to FastAPI.")
            print("Make sure FastAPI is running on:", API_URL)
            return failed_result("FastAPI unavailable.")

        except requests.exceptions.Timeout:
            print("FastAPI request timed out.")
            print(
                "The activity was not confirmed by FastAPI within "
                "the collector timeout."
            )
            return failed_result("FastAPI request timed out.")

        except requests.exceptions.RequestException as error:
            print("FastAPI request error:", error)
            return failed_result("Activity request failed.")

        except Exception as error:
            print("FastAPI activity error:", error)
            return failed_result("Activity request failed.")

    if response is None:
        return failed_result("FastAPI request failed.")

    # -------------------------------------------------
    # RESPONSE JSON
    # -------------------------------------------------

    try:
        response_data = response.json()
    except Exception:
        response_data = {}

    if response.status_code == 401:
        print("FastAPI Error: 401 Unauthorized")
        print("Collector authentication failed.")
        print("Log in to FocusSense again to refresh collector_token.txt.")
        return failed_result("Collector authentication failed.")

    if response.status_code != 200:
        print("FastAPI Error:", response.status_code)

        try:
            print("FastAPI Response:", response.text)
        except Exception:
            pass

        return failed_result("FastAPI request failed.")

    if not isinstance(response_data, dict):
        response_data = {}

    ai_result = response_data.get("ai_classification", {})
    if not isinstance(ai_result, dict):
        ai_result = {}

    activity_result = response_data.get("activity", {})
    if not isinstance(activity_result, dict):
        activity_result = {}

    # Backend flags are authoritative for the recording mode.
    recorded = bool(response_data.get("recorded", False))
    live_only = bool(response_data.get("live_only", False))
    active_session = bool(response_data.get("active_session", False))

    # -------------------------------------------------
    # LIVE-ONLY OVERRIDE
    # -------------------------------------------------
    # Prevent stale Java/Python/etc. context from a previous
    # study session from being displayed when no session is active.
    if live_only or not recorded:
        classification = "Neutral"
        confidence = 0.0
        reason = (
            "No active study session. Activity is shown live "
            "but is not recorded."
        )
        pattern = ""
        evidence = "Activity is shown live but is not recorded."
        active_session = False
    else:
        classification = ai_result.get(
            "classification",
            activity_result.get("classification", "Neutral")
        )

        if not classification:
            classification = "Neutral"

        confidence = ai_result.get("confidence", 0.0)
        reason = ai_result.get("reason", "")
        pattern = ai_result.get("pattern", "")
        evidence = ai_result.get("evidence", "")

    # -------------------------------------------------
    # CANONICAL TIMESTAMPS
    # -------------------------------------------------

    response_start = activity_result.get("start_time")
    response_end = activity_result.get("end_time")

    print("--------------------------------")
    print("Sent to FastAPI: SUCCESS")
    print(
        "Activity Start:",
        response_start or format_local_datetime(safe_start)
    )
    print(
        "Activity End  :",
        response_end or format_local_datetime(safe_end)
    )

    print("AI Classification:", classification)
    print("AI Confidence:", confidence)
    print("AI Reason:", reason)

    # Pattern is shown only for actual recorded study activities.
    if pattern and not live_only and recorded:
        print("AI Pattern:", pattern)

    if evidence:
        print("AI Evidence:", evidence)

    if live_only or not recorded:
        print("Mode: LIVE ONLY - activity was displayed but NOT recorded")
    else:
        print("Mode: RECORDED - activity saved by FastAPI")

    print("--------------------------------")

    return {
        "success": True,
        "classification": classification,
        "confidence": confidence,
        "reason": reason,
        "pattern": pattern,
        "evidence": evidence,
        "recorded": recorded,
        "live_only": live_only,
        "active_session": active_session,
    }


# =====================================================
# PROCESS COMPLETED ACTIVITY
# =====================================================

def process_completed_activity(
    application,
    window_title,
    start_timestamp,
    end_timestamp
):
    """Measure one activity interval and send it to FastAPI."""

    try:
        start_timestamp = float(start_timestamp)
        end_timestamp = float(end_timestamp)
    except (TypeError, ValueError):
        print("Invalid activity timestamps. Activity skipped.")
        return False

    duration = max(end_timestamp - start_timestamp, 0.0)
    duration = round(duration, 2)

    if duration < MIN_ACTIVITY_DURATION:
        print(
            "Skipped short activity:",
            application,
            "|",
            window_title,
            "|",
            duration,
            "seconds"
        )
        return False

    print("--------------------------------")
    print("Activity:", application)
    print("Window:", window_title)
    print("Start:", format_local_datetime(start_timestamp))
    print("End:", format_local_datetime(end_timestamp))
    print("Duration:", duration, "seconds")
    print("Sending activity to FastAPI AI...")

    result = send_activity_to_fastapi(
        application,
        window_title,
        duration,
        start_timestamp,
        end_timestamp,
    )

    if not result.get("success", False):
        print(
            "Activity was not confirmed by FastAPI, "
            "so the collector did not save a local copy."
        )
        print("--------------------------------")
        return False

    if result.get("live_only", False) or not result.get("recorded", False):
        print(
            "Current activity was handled as LIVE ONLY; "
            "FastAPI persistence was skipped."
        )
        print("--------------------------------")
        return True

    # No local CSV write happens here.
    # FastAPI writes user CSV + MongoDB exactly once.
    print(
        "FastAPI confirmed recorded activity; "
        "no duplicate local CSV write."
    )
    print("--------------------------------")
    return True


# =====================================================
# BACKGROUND FASTAPI SENDER
# =====================================================
# Network calls to FastAPI are processed on a dedicated worker thread.
# This prevents a slow/temporarily unavailable FastAPI or Groq request from
# blocking Windows activity detection in the main loop.

activity_queue = Queue()


def activity_sender_worker():
    """Process queued activities without blocking the collector loop."""

    while True:
        job = activity_queue.get()

        try:
            if job is None:
                return

            try:
                process_completed_activity(*job)
            except Exception as error:
                # One bad request/activity must never terminate the worker.
                print(
                    "Background activity processing error:",
                    error,
                    flush=True,
                )
        finally:
            activity_queue.task_done()


activity_sender_thread = threading.Thread(
    target=activity_sender_worker,
    name="FocusSense-FastAPI-Sender",
    daemon=True,
)
activity_sender_thread.start()


# =====================================================
# ACTIVITY MONITORING STATE
# =====================================================

previous_app = None
previous_title = None
start_timestamp = None


# =====================================================
# START MESSAGE
# =====================================================

print("========================================")
print("FocusSense Activity Collector Started")
print("FastAPI:", API_URL)
print("Activity Endpoint:", ACTIVITY_ENDPOINT)
print("Token File:", TOKEN_FILE)
print("AI Classification: HANDLED BY FASTAPI BACKEND")
print("AI Engine: Groq + FastAPI context-aware classifier")
print("Detection Classes: Productive / Distractive / Neutral")
print("Activity persistence: HANDLED BY FASTAPI")
print("Live-only behavior: HANDLED BY FASTAPI")
print("Live-only stale-context protection: ENABLED")
print("Exact timestamps: ENABLED")
print("Minimum activity duration:", MIN_ACTIVITY_DURATION, "seconds")
print("Poll interval:", POLL_INTERVAL, "seconds")
print("Backend request timeout:", API_TIMEOUT, "seconds")
print("Connection retries:", MAX_REQUEST_RETRIES)
print("Background FastAPI sender: ENABLED")

if get_collector_token():
    print("Collector authentication: AVAILABLE")
else:
    print("Collector authentication: NOT FOUND")
    print("Log in to FocusSense before expecting recorded activities.")

print("Press Ctrl+C to stop.")
print("========================================")


# =====================================================
# MAIN LOOP
# =====================================================

try:
    while True:
        application, window_title = get_active_window_info()
        current_timestamp = time.time()

        # -------------------------------------------------
        # FIRST ACTIVITY
        # -------------------------------------------------

        if previous_app is None:
            previous_app = application
            previous_title = window_title
            start_timestamp = current_timestamp

        # -------------------------------------------------
        # ACTIVE WINDOW CHANGED
        # -------------------------------------------------

        elif (
            application != previous_app
            or window_title != previous_title
        ):
            activity_queue.put((
                previous_app,
                previous_title,
                start_timestamp,
                current_timestamp,
            ))

            previous_app = application
            previous_title = window_title
            start_timestamp = current_timestamp

        # -------------------------------------------------
        # NO WINDOW CHANGE
        # -------------------------------------------------

        time.sleep(POLL_INTERVAL)


# =====================================================
# STOP COLLECTOR
# =====================================================

except KeyboardInterrupt:
    current_timestamp = time.time()

    # Queue the final unfinished activity without waiting for FastAPI.
    if (
        previous_app is not None
        and previous_title is not None
        and start_timestamp is not None
    ):
        try:
            activity_queue.put_nowait((
                previous_app,
                previous_title,
                start_timestamp,
                current_timestamp,
            ))
        except Exception:
            pass

    # Tell the worker to finish after the queued final activity. Do not wait
    # for the network request: FastAPI/Groq must never block collector shutdown.
    try:
        activity_queue.put_nowait(None)
    except Exception:
        pass

    print("\n========================================")
    print("FocusSense Activity Collector stopped safely.")
    print("Current unfinished activity was queued for final processing.")
    print("========================================")

finally:
    try:
        http_session.close()
    except Exception:
        pass
