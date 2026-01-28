"""
Google Gemini Live API 클라이언트 (Pure Translator Mode)
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
    """Google Gemini Live API 클라이언트 (STRICT Translator Only)"""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash-native-audio-latest", 
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
        """전문 번역사 모드 (말대꾸 금지)"""
        return f"Translator mode. Output only text in {self.target_lang}. No talk. No intro. No commentary. Immediate translation."

    async def connect(self, **kwargs):
        """Websocket 연결"""
        try:
            self._change_state(ClientState.CONNECTING)
            self.setup_done.clear()

            url = f"{APIEndpoints.GOOGLE_GEMINI_LIVE}?key={self.api_key}"
            self._log("connection", f"Connecting Pure Translator (Model: {self.model})")
            
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
        """세션 구성 (전사 옵션 강제 활성)"""
        config_message = {
            "setup": {
                "model": f"models/{self.model}",
                "generation_config": {
                    "response_modalities": ["AUDIO"]
                },
                "system_instruction": {
                    "parts": [{"text": self.system_prompt}]
                },
                # 전사 결과를 서버에서 직접 받기 위해 명시적으로 빈 객체 전달
                "input_audio_transcription": {}
            }
        }
        await self.ws.send(json.dumps(config_message))

    async def send_audio(self, audio_data: bytes):
        """오디오 송신"""
        if not self.ws or self.state not in [ClientState.CONNECTED, ClientState.LISTENING]:
            return

        try:
            if not self.setup_done.is_set():
                await asyncio.wait_for(self.setup_done.wait(), timeout=5.0)

            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            message = {
                "realtime_input": {
                    "media_chunks": [{"mime_type": "audio/pcm;rate=16000", "data": audio_b64}]
                }
            }
            await self.ws.send(json.dumps(message))
            if self.session_start_time is None: self.session_start_time = time.time()
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
        """수신 데이터 처리 (설명글 필터링 로직 포함)"""
        # (1) Handshake
        if any(k in data for k in ["setupComplete", "setup_complete"]):
            self.setup_done.set()
            return

        # (2) Error
        if "error" in data:
            self._emit_error(Exception(data["error"].get("message", "Unknown Error")))
            return

        # (3) Content
        content = data.get("serverContent") or data.get("server_content")
        if not content: return

        # A. 전사 결과 (입력 음성 데이터 인식)
        for key in ["inputTranscription", "input_transcription"]:
            trans = content.get(key)
            if trans:
                text = trans.get("text", "")
                if text: self._emit_transcription(text)

        # B. 모델 답변 (번역 결과)
        # 만약 모델이 마음대로 떠들면, 특정 키워드(I've, Translating, 안녕하세요 등 대답)를 필터링하는 대신 
        # modelTurn의 text를 그대로 보내되 프롬프트로 제어
        turn = content.get("modelTurn") or content.get("model_turn")
        if turn:
            for part in turn.get("parts", []):
                if "text" in part:
                    text = part["text"].replace("**", "").replace("###", "").strip()
                    if text:
                        if self.mode in ["translation", "both"]:
                            self._emit_translation(text)
                        else:
                            self._emit_transcription(text)
                elif any(k in part for k in ["inlineData", "inline_data"]):
                    obj = part.get("inlineData") or part.get("inline_data")
                    audio_raw = base64.b64decode(obj.get("data", ""))
                    self.stats['total_audio_received_seconds'] += len(audio_raw) / (24000 * 2)

    async def disconnect(self):
        """해제"""
        try:
            if hasattr(self, 'receive_task'): self.receive_task.cancel()
            if self.ws: await self.ws.close()
            self._change_state(ClientState.CLOSED)
        except: pass

    def get_cost_estimate(self) -> Dict[str, float]:
        return {'service': 'gemini', 'total_cost_usd': 0.0}
