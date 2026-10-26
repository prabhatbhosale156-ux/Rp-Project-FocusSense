
import os
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

# Load .env directly from the BackEnd folder.
env_path = Path(__file__).resolve().with_name(".env")
print("Environment file exists:", env_path.is_file())

if not env_path.is_file():
    raise SystemExit(
        "ERROR: Create .env beside test_groq.py"
    )

# Override any older GROQ_API_KEY stored in Windows.
load_dotenv(dotenv_path=env_path, override=True)

api_key = os.getenv("GROQ_API_KEY", "").strip()

print("API key loaded:", bool(api_key))
print("Key starts with gsk_:", api_key.startswith("gsk_"))
print("Key length:", len(api_key))

if not api_key:
    raise SystemExit("ERROR: GROQ_API_KEY is empty.")

try:
    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model=os.getenv(
            "GROQ_MODEL",
            "llama-3.3-70b-versatile"
        ),
        messages=[
            {
                "role": "user",
                "content": "Reply with exactly: CONNECTION SUCCESS"
            }
        ],
        temperature=0,
        max_tokens=20,
    )

    print("SUCCESS: Groq API connected!")
    print(response.choices[0].message.content)

except Exception as exc:
    print("Groq error:", type(exc).__name__)

    if getattr(exc, "status_code", None) == 401:
        print("The key was rejected by Groq.")
        print("Check that you copied the complete, active API key.")
    else:
        print(str(exc))
