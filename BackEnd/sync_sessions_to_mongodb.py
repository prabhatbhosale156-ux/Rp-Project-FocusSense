import csv
import os
from pymongo import MongoClient

# ==========================================
# PATHS
# ==========================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

CSV_FILE = os.path.join(
    BASE_DIR,
    "study_sessions.csv"
)

# ==========================================
# MONGODB
# ==========================================

MONGO_URI = "mongodb://localhost:27017"

client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000
)

client.admin.command("ping")

db = client["focussense"]

collection = db["study_sessions"]

print("MongoDB connected.")
print("CSV:", CSV_FILE)

# ==========================================
# GET EXISTING SESSION NUMBERS
# ==========================================

existing_numbers = set()

for document in collection.find(
    {},
    {"_id": 0, "session_number": 1}
):
    try:
        existing_numbers.add(
            int(document.get("session_number"))
        )
    except:
        pass

print(
    "Existing MongoDB session numbers:",
    sorted(existing_numbers)
)

# ==========================================
# READ CSV
# ==========================================

if not os.path.exists(CSV_FILE):
    print("ERROR: study_sessions.csv not found.")
    client.close()
    raise SystemExit

missing_sessions = []

with open(
    CSV_FILE,
    "r",
    encoding="utf-8-sig",
    newline=""
) as file:

    reader = csv.DictReader(file)

    for row in reader:

        try:
            session_number = int(
                str(
                    row.get(
                        "Session Number",
                        ""
                    )
                ).strip()
            )
        except:
            continue

        # Only insert missing sessions
        if session_number in existing_numbers:
            continue

        try:
            duration = float(
                row.get(
                    "Duration (seconds)",
                    0
                )
            )
        except:
            duration = 0.0

        document = {
            "session_number": session_number,
            "subject": str(
                row.get(
                    "Subject",
                    ""
                )
            ).strip(),
            "goal": str(
                row.get(
                    "Goal",
                    ""
                )
            ).strip(),
            "duration": duration,
            "date": str(
                row.get(
                    "Date",
                    ""
                )
            ).strip(),
            "time": str(
                row.get(
                    "Time",
                    ""
                )
            ).strip()
        }

        missing_sessions.append(document)

# ==========================================
# INSERT MISSING SESSIONS
# ==========================================

if not missing_sessions:

    print("No missing sessions found.")

else:

    print(
        "Sessions to insert:",
        [
            x["session_number"]
            for x in missing_sessions
        ]
    )

    collection.insert_many(
        missing_sessions
    )

    print(
        "Inserted:",
        len(missing_sessions),
        "sessions."
    )

# ==========================================
# VERIFY
# ==========================================

total = collection.count_documents({})

print(
    "Total MongoDB study_sessions:",
    total
)

numbers = sorted(
    int(
        x["session_number"]
    )
    for x in collection.find(
        {},
        {"_id": 0, "session_number": 1}
    )
    if str(
        x.get("session_number", "")
    ).isdigit()
)

print(
    "MongoDB session numbers:",
    numbers
)

client.close()

print("Synchronization completed.")