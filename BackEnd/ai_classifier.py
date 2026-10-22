import json
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI


MODEL = "gpt-5.6-luna"

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def classify_activity(
    application: str,
    window: str,
    duration: float,
    subject: str = "",
    goal: str = "",
    recent_activities: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Classify a computer activity as Productive, Neutral, or Distractive
    using the current study context and observable activity information.
    """

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    recent_activities = recent_activities or []

    recent_text = "\n".join(
        [
            (
                f"- Application: {item.get('application', '')}, "
                f"Window: {item.get('window', '')}, "
                f"Duration: {item.get('duration', 0)} seconds, "
                f"Classification: {item.get('classification', '')}"
            )
            for item in recent_activities[-10:]
        ]
    )

    if not recent_text:
        recent_text = "No previous activity available."

    prompt = f"""
You are the activity-classification engine for FocusSense,
a context-aware student study behavior intelligence system.

Determine whether the CURRENT computer activity is:

1. Productive
2. Neutral
3. Distractive

Use the student's current study context.

STUDY CONTEXT
Subject: {subject or "Not provided"}
Study Goal: {goal or "Not provided"}

CURRENT ACTIVITY
Application: {application}
Window Title: {window}
Duration: {duration} seconds

RECENT ACTIVITY
{recent_text}

IMPORTANT RULES

- Judge the activity based on the study subject and study goal.
- Do NOT classify an entire application as always productive or always distractive.
- The same website/application may be productive in one context and distractive in another.
- Example:
  YouTube + "Python Functions" can be Productive.
  YouTube + unrelated gaming content during Python study can be Distractive.
- Programming tools such as VS Code may be Productive when related to the study goal.
- A short task-switching event may be Neutral.
- Base the decision only on observable information.
- Do not claim to know the student's emotions, thoughts, intentions, or mental state.
- Do not invent information that is not present.
- The reason must describe observable evidence.
- Confidence must be a number from 0 to 1.
- Return only valid JSON.
"""

    response = client.responses.create(
        model=MODEL,
        input=prompt,
    )

    raw_output = response.output_text.strip()

    try:
        result = json.loads(raw_output)
    except json.JSONDecodeError:
        return {
            "classification": "Neutral",
            "confidence": 0.0,
            "reason": "AI returned an invalid classification response.",
            "pattern": "Unknown",
            "evidence": raw_output[:500],
        }

    classification = str(
        result.get("classification", "Neutral")
    ).capitalize()

    if classification not in {
        "Productive",
        "Neutral",
        "Distractive",
    }:
        classification = "Neutral"

    try:
        confidence = float(result.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    confidence = max(0.0, min(1.0, confidence))

    return {
        "classification": classification,
        "confidence": confidence,
        "reason": str(
            result.get(
                "reason",
                "No reason provided.",
            )
        ),
        "pattern": str(
            result.get(
                "pattern",
                "No pattern identified.",
            )
        ),
        "evidence": str(
            result.get(
                "evidence",
                "No evidence provided.",
            )
        ),
    }