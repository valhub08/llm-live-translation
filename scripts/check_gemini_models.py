import google.generativeai as genai
import os
from dotenv import load_dotenv
from pathlib import Path

# .env 로드
load_dotenv(Path(__file__).parent.parent / 'config' / '.env')
api_key = os.getenv('GOOGLE_API_KEY')

if not api_key:
    print("API Key not found.")
    exit(1)

genai.configure(api_key=api_key)

print("Available Gemini Models:")
try:
    for m in genai.list_models():
        if 'bidiGenerateContent' in m.supported_generation_methods:
            print(f"- {m.name} (Live API Supported)")
        elif 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Error: {e}")
