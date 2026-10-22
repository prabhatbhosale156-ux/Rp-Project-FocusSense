import os
from openai import OpenAI

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError("OPENAI_API_KEY is not set.")

client = OpenAI(api_key=api_key)

response = client.responses.create(
    model="gpt-5.6-luna",
    input="Reply with exactly: FocusSense AI API is working."
)

print(response.output_text)