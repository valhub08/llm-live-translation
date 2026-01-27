import os
import requests
from dotenv import load_dotenv
from pathlib import Path

# .env 파일 로드
load_dotenv(Path('config/.env'))
api_key = os.getenv('OPENAI_API_KEY')

def test_models():
    if not api_key:
        print("OPENAI_API_KEY not found in config/.env")
        return

    url = "https://api.openai.com/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            models = response.json().get('data', [])
            realtime_models = [m['id'] for m in models if 'realtime' in m['id']]
            print("Available Realtime Models:")
            for m in realtime_models:
                print(f" - {m}")
            
            if not realtime_models:
                print("No realtime models found for this key.")
        else:
            print(f"Error fetching models: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_models()
