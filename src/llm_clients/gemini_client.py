"""
Google Gemini Live API 클라이언트 (가장 처음에 잘 되었던 초기 버전 기반)
"""

import asyncio
import json
import base64
import time
from typing import Optional, Dict, Any
from pathlib import Path
import sys
import websockets

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.llm_clients.base_client import BaseLLMClient, ClientState
from src.utils.logger import EventLogger
from config.settings import APIEndpoints, AudioConfig, PromptTemplates, CostConfig


class GeminiLiveClient(BaseLLMClient):
    """Google Gemini Live API 클라이언트 (최초 작동 버전 복원)"""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash-exp",
        mode: str = "transcription",
        source_lang: str = "ko",
        target_lang: str = "en",
        glossary: Optional[str] = None,
        logger: Optional[EventLogger] = None,
        **kwargs
    ):
        super().__init__(api_key, logger, **kwargs)

        self.model = model
        self.mode = mode
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.glossary = glossary
        self.system_prompt = self._get_system_prompt()

        self.session_start_time = None
        self.setup_done = asyncio.Event()

    def _get_system_prompt(self) -> str:
        """모드에 따른 실시간 번역 지침"""
        if self.mode == "transcription":
            return f"Transcribe exactly what you hear in {self.source_lang}."
        elif self.mode == "translation":
            return f"Translate {self.source_lang} to {self.target_lang} immediately."
        else: # both
            return f"First transcribe in {self.source_lang}, then translate into {self.target_lang}."

    async def connect(self, **kwargs):
        """Websocket 연결"""
        try:
            self._change_state(ClientState.CONNECTING)
            self.setup_done.clear()

            url = f"{APIEndpoints.GOOGLE_GEMINI_LIVE}?key={self.api_key}"
            self._log("connection", f"Connecting to {self.model}")
            
            self.ws = await websockets.connect(
                url, 
                origin="https://generativelanguage.googleapis.com"
            )

            self._change_state(ClientState.CONNECTED)
            self._log("connection", "Connected successfully")

            self.receive_task = asyncio.create_task(self.receive_messages())
            await self._configure_session()

        except Exception as e:
            self._change_state(ClientState.ERROR)
            self._emit_error(e, {"location": "connect"})
            raise

    async def _configure_session(self):
        """세션 구성 (최소 화한 필수 구조)"""
        # 1007 에러 근본 차단: 부가 필드를 절대 넣지 않음
        config_message = {
            "setup": {
                "model": f"models/{self.model}",
                "system_instruction": {
                    "parts": [{"text": self.system_prompt}]
                }
            }
        }
        await self.ws.send(json.dumps(config_message))

    async def send_audio(self, audio_data: bytes):
        """오디오 데이터 전송"""
        if not self.ws or self.state not in [ClientState.CONNECTED, ClientState.LISTENING]:
            return

        try:
            if not self.setup_done.is_set():
                await asyncio.wait_for(self.setup_done.wait(), timeout=5.0)

            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            # realtime_input (가장 안정적인 규격)
            message = {
                "realtime_input": {
                    "media_chunks": [
                        {
                            "mime_type": "audio/pcm;rate=16000",
                            "data": audio_b64
                        }
                    ]
                }
            }
            await self.ws.send(json.dumps(message))
            
            if self.session_start_time is None:
                self.session_start_time = time.time()
            
        except Exception as e:
            self._emit_error(e, {"location": "send_audio"})

    async def receive_messages(self):
        """수신 루프"""
        try:
            self._change_state(ClientState.LISTENING)
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except Exception as e:
                    self._emit_error(e, {"location": "parsing"})
        except Exception as e:
            self._change_state(ClientState.ERROR)

    async def _handle_message(self, data: Dict[str, Any]):
        """수신 데이터 처리"""
        # (1) Setup 완료
        if any(k in data for k in ["setupComplete", "setup_complete"]):
            self.setup_done.set()
            self._log("session", "Setup complete")
            return

        # (2) 오류
        if "error" in data:
            self._emit_error(Exception(data["error"].get("message", "API Error")))
            return

        # (3) 콘텐츠 파싱
        content = data.get("serverContent") or data.get("server_content")
        if not content: return

        # (A) 전사 결과 수집
        for key in ["inputTranscription", "input_transcription", "outputTranscription", "output_transcription"]:
            trans = content.get(key)
            if trans:
                text = trans.get("text", "")
                if text:
                    if "output" in key and self.mode in ["translation", "both"]:
                        self._emit_translation(text)
                    else:
                        self._emit_transcription(text)

        # (B) 모델 턴 (델타 텍스트)
        turn = content.get("modelTurn") or content.get("model_turn")
        if turn:
            for part in turn.get("parts", []):
                if "text" in part:
                    text = part["text"]
                    if self.mode in ["translation", "both"]:
                        self._emit_translation(text)
                    else:
                        self._emit_transcription(text)
                elif any(k in part for k in ["inlineData", "inline_data"]):
                    obj = part.get("inlineData") or part.get("inline_data")
                    audio_raw = base64.b64decode(obj.get("data", ""))
                    self.stats['total_audio_received_seconds'] += len(audio_raw) / (24000 * 2)

    async def disconnect(self):
        """정지"""
        try:
            if hasattr(self, 'receive_task'): self.receive_task.cancel()
            if self.ws: await self.ws.close()
            self._change_state(ClientState.CLOSED)
        except: pass

    def get_cost_estimate(self) -> Dict[str, float]:
        return {'service': 'gemini', 'total_cost_usd': 0.0}
