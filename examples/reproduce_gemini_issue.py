import asyncio
import json
import base64
import websockets
import os
from dotenv import load_dotenv

load_dotenv("config/.env")
api_key = os.getenv("GOOGLE_API_KEY")

async def test_gemini_handshake():
    url = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={api_key}"
    
    headers = {
        "Origin": "https://generativelanguage.googleapis.com"
    }

    print(f"Connecting to {url}...")
    try:
        async with websockets.connect(url, origin=headers["Origin"]) as ws:
            print("Connected successfully.")
            
            # 1. Setup message (Strict camelCase, AUDIO only + Transcription)
            setup_msg = {
                "setup": {
                    "model": "models/gemini-2.0-flash-exp",
                    "generationConfig": {
                        "responseModalities": ["AUDIO"]
                    },
                    "systemInstruction": {
                        "parts": [{"text": "You are a transcription system. Just transcribe the audio you hear."}]
                    }
                }
            }
            
            print(f"Sending setup: {json.dumps(setup_msg)}")
            await ws.send(json.dumps(setup_msg))
            
            # 2. Wait for server response
            try:
                # 10초 동안 서버의 응답을 기다림
                while True:
                    response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    data = json.loads(response)
                    print(f"Received from server: {json.dumps(data, indent=2)}")
                    
                    if "setupComplete" in data:
                        print("[Done] Setup handshake SUCCESSFUL!")
                        break
                    
                    if "error" in data:
                        print(f"[Error] Server returned error: {data['error']}")
                        break
            except asyncio.TimeoutError:
                print("⏳ Timeout waiting for setupComplete.")
            except websockets.exceptions.ConnectionClosed as e:
                print(f"🔌 Connection closed: {e.code} ({e.reason})")

    except Exception as e:
        print(f"💥 Fatal error: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini_handshake())
