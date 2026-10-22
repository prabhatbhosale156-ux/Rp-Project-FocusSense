from ai_classifier import classify_activity


result = classify_activity(
    application="code.exe",
    window="Python Functions - Visual Studio Code",
    duration=35,
    subject="Python",
    goal="Learn Functions",
    recent_activities=[
        {
            "application": "msedge.exe",
            "window": "Python functions tutorial",
            "duration": 40,
            "classification": "Productive",
        },
        {
            "application": "code.exe",
            "window": "Python Functions - Visual Studio Code",
            "duration": 35,
            "classification": "Productive",
        },
    ],
)

print("\nAI CLASSIFICATION RESULT")
print("------------------------")
print("Classification:", result["classification"])
print("Confidence:", result["confidence"])
print("Reason:", result["reason"])
print("Pattern:", result["pattern"])
print("Evidence:", result["evidence"])