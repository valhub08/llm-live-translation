"""
OpenAI Realtime API 클라이언트
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


class OpenAIRealtimeClient(BaseLLMClient):
    """OpenAI Realtime API 클라이언트"""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-realtime-mini-2025-12-15",
        mode: str = "transcription",  # 'transcription', 'translation', 'both'


        source_lang: str = "en",
        target_lang: str = "ko",
        glossary: Optional[str] = None,
        logger: Optional[EventLogger] = None,
        **kwargs
    ):
        """
        Args:
            api_key: OpenAI API 키
            model: 모델 이름
            mode: 동작 모드 ('transcription', 'translation', 'both')
            source_lang: 소스 언어
            target_lang: 타겟 언어
            glossary: 용어집 또는 추가 지침 (프롬프트에 추가됨)
            logger: EventLogger 인스턴스
            **kwargs: 추가 설정
        """
        super().__init__(api_key, logger, **kwargs)

        self.model = model
        self.mode = mode
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.glossary = glossary

        # 프롬프트 선택
        self.system_prompt = self._get_system_prompt()

        # 세션 설정
        self.session_config = {
            "modalities": ["text", "audio"],
            "instructions": self.system_prompt,
            "voice": "alloy",
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": {
                "model": "whisper-1"
            },
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500
            },
            "temperature": 0.8,
        }

        # 비용 추적
        self.audio_input_seconds = 0
        self.audio_output_seconds = 0

    def _get_system_prompt(self) -> str:
        """모드에 따른 시스템 프롬프트 반환"""
        base_prompt = ""
        if self.mode == "transcription":
            base_prompt = PromptTemplates.OPENAI_TRANSCRIPTION_ONLY

        elif self.mode == "translation":
            base_prompt = PromptTemplates.OPENAI_TRANSLATION_ONLY.format(
                source_lang=self.source_lang,
                target_lang=self.target_lang
            )

        elif self.mode == "both":
            base_prompt = PromptTemplates.OPENAI_TRANSCRIPTION_AND_TRANSLATION.format(
                source_lang=self.source_lang,
                target_lang=self.target_lang
            )
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

        # 용어집 추가
        if self.glossary:
            base_prompt += f"\n\nGLOSSARY / ADDITIONAL INSTRUCTIONS:\n{self.glossary}"

        return base_prompt

    async def connect(self, **kwargs):
        """OpenAI Realtime API에 연결"""
        try:
            self._change_state(ClientState.CONNECTING)

            # WebSocket URL 구성
            url = f"{APIEndpoints.OPENAI_REALTIME}?model={self.model}"

            # 헤더 설정
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }

            # 연결
            self._log("connection", f"Connecting to {url}")
            self.ws = await websockets.connect(url, additional_headers=headers)

            self._change_state(ClientState.CONNECTED)
            self._log("connection", "Connected successfully")

            # 세션 설정 전송
            await self._configure_session()

            self.stats['connection_time'] = time.time()

        except Exception as e:
            self._change_state(ClientState.ERROR)
            self._emit_error(e, {"location": "connect"})
            raise

    async def _configure_session(self):
        """세션 설정"""
        config_message = {
            "type": "session.update",
            "session": self.session_config
        }

        await self.ws.send(json.dumps(config_message))
        self._log("config", "Session configured")

    async def disconnect(self):
        """연결 해제"""
        try:
            if self.ws:
                await self.ws.close()
                self._log("connection", "Disconnected")

            self._change_state(ClientState.CLOSED)
            self.stats['disconnection_time'] = time.time()

        except Exception as e:
            self._emit_error(e, {"location": "disconnect"})

    async def send_audio(self, audio_data: bytes):
        """
        오디오 데이터 전송

        Args:
            audio_data: PCM16 오디오 데이터 (16-bit, 24kHz, mono)
        """
        if not self.ws or self.state not in [ClientState.CONNECTED, ClientState.LISTENING]:
            # self._log("warning", "Not connected, skipping audio send")
            return

        try:
            # Base64 인코딩
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')

            # 메시지 구성
            message = {
                "type": "input_audio_buffer.append",
                "audio": audio_b64
            }

            await self.ws.send(json.dumps(message))

            # 통계 업데이트 (대략적 계산)
            duration_seconds = len(audio_data) / (AudioConfig.OPENAI_SAMPLE_RATE * 2)  # 16-bit = 2 bytes
            self.audio_input_seconds += duration_seconds
            self.stats['total_audio_sent_seconds'] = self.audio_input_seconds

        except Exception as e:
            self._emit_error(e, {"location": "send_audio"})

    async def receive_messages(self):
        """메시지 수신 루프"""
        try:
            self._change_state(ClientState.LISTENING)

            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)

                except json.JSONDecodeError as e:
                    self._emit_error(e, {"location": "receive_messages", "message": "JSON decode error"})
                except Exception as e:
                    self._emit_error(e, {"location": "receive_messages"})

        except websockets.exceptions.ConnectionClosed:
            self._log("connection", "Connection closed by server")
            self._change_state(ClientState.DISCONNECTED)
        except Exception as e:
            self._emit_error(e, {"location": "receive_messages_loop"})
            self._change_state(ClientState.ERROR)

    async def _handle_message(self, data: Dict[str, Any]):
        """수신 메시지 처리"""
        msg_type = data.get("type", "")

        # 세션 생성
        if msg_type == "session.created":
            self._log("session", "Session created", session_id=data.get("session", {}).get("id"))

        # 세션 업데이트
        elif msg_type == "session.updated":
            self._log("session", "Session updated")

        # 입력 오디오 버퍼 커밋됨
        elif msg_type == "input_audio_buffer.committed":
            self._log("audio_input", "Audio buffer committed")

        # 입력 오디오 버퍼 전사 성공
        elif msg_type == "conversation.item.input_audio_transcription.completed":
            transcript = data.get("transcript", "")
            self._emit_transcription(transcript, {"source": "input_transcription"})

        # 입력 오디오 버퍼 전사 실패
        elif msg_type == "conversation.item.input_audio_transcription.failed":
            error = data.get("error", {})
            msg = error.get("message", "Transcription failed")
            self._log("audio_transcription_failed", msg, error_details=error)
            # self._emit_error(Exception(f"Transcription failed: {msg}"), {"type": "transcription_failed"})

        # 응답 텍스트 델타
        elif msg_type == "response.text.delta":
            delta = data.get("delta", "")
            # 'both' 모드에서는 파싱이 필요할 수 있지만, 우선 그대로 전달
            if self.mode == "translation":
                self._emit_translation(delta, {"type": "delta"})
            elif self.mode == "transcription":
                self._emit_transcription(delta, {"type": "delta"})
            else:
                # 'both' 모드 등
                self._emit_transcription(delta, {"type": "delta", "mode": self.mode})

        # 응답 텍스트 완료
        elif msg_type == "response.text.done":
            text = data.get("text", "")
            if self.mode == "both":
                self._parse_and_emit_both(text)
            elif self.mode == "translation":
                self._emit_translation(text, {"type": "done"})
            else:
                self._emit_transcription(text, {"type": "done"})

        # 응답 오디오
        elif msg_type == "response.audio.delta":
            audio_b64 = data.get("delta", "")
            audio_bytes = base64.b64decode(audio_b64)
            duration = len(audio_bytes) / (AudioConfig.OPENAI_SAMPLE_RATE * 2)
            self.audio_output_seconds += duration
            self.stats['total_audio_received_seconds'] = self.audio_output_seconds

        # 오디오 전사 델타 (TTS 결과의 전사 = 실시간 번역)
        elif msg_type == "response.audio_transcript.delta":
            delta = data.get("delta", "")
            # 번역 모드에서는 이것이 실시간 번역 결과
            if self.mode in ["translation", "both"]:
                self._emit_translation(delta, {"type": "delta"})

        # 오디오 전사 완료
        elif msg_type == "response.audio_transcript.done":
            transcript = data.get("transcript", "")
            if self.mode == "both":
                self._parse_and_emit_both(transcript)
            elif self.mode == "translation":
                self._emit_translation(transcript, {"type": "done"})
            else:
                self._emit_transcription(transcript, {"type": "done"})

        # 에러
        elif msg_type == "error":
            error_data = data.get("error", {})
            error_msg = error_data.get("message", "Unknown error")
            self._emit_error(Exception(error_msg), {"error_data": error_data})

        # 기타 메시지
        elif msg_type == "response.created":
            self._log("response_created", "Response created", response_id=data.get("response", {}).get("id"))
            
        elif msg_type == "response.done":
            response = data.get("response", {})
            status = response.get("status", "")
            self._log("response_done", f"Response done (status: {status})", response=response)
            if status == "failed":
                error = response.get("status_details", {}).get("error", {})
                self._emit_error(Exception(f"Response failed: {error.get('message')}"))

        else:
            if msg_type not in ["rate_limits.updated"]:
                self._log("message", f"Received: {msg_type}")



    def _parse_and_emit_both(self, text: str):
        """[ORIGINAL] ... [TRANSLATION] ... 형식의 텍스트 파싱"""
        original = ""
        translation = ""

        # 줄 단위로 처리하거나 태그 기준으로 분할
        if "[ORIGINAL]" in text:
            parts = text.split("[TRANSLATION]")
            original = parts[0].replace("[ORIGINAL]", "").strip()
            if len(parts) > 1:
                translation = parts[1].strip()
        elif "[TRANSLATION]" in text:
            translation = text.replace("[TRANSLATION]", "").strip()
        else:
            # 형식이 없으면 번역으로 간주 (또는 전사)
            translation = text

        if original:
            self._emit_transcription(original, {"type": "final", "parsed": True})
        if translation:
            self._emit_translation(translation, {"type": "final", "parsed": True})

    def get_cost_estimate(self) -> Dict[str, float]:
        """현재까지 사용한 비용 추정"""
        # 1분 = 대략 6000 tokens (입력)
        input_tokens = self.audio_input_seconds * 100 
        output_tokens = self.audio_output_seconds * 200

        input_cost_realtime = (input_tokens / 1_000_000) * CostConfig.OPENAI_AUDIO_INPUT_REALTIME_PRICE
        output_cost_realtime = (output_tokens / 1_000_000) * CostConfig.OPENAI_AUDIO_OUTPUT_REALTIME_PRICE

        return {
            'service': 'openai',
            'input_seconds': round(self.audio_input_seconds, 2),
            'output_seconds': round(self.audio_output_seconds, 2),
            'input_cost_usd': round(input_cost_realtime, 6),
            'output_cost_usd': round(output_cost_realtime, 6),
            'total_cost_usd': round(input_cost_realtime + output_cost_realtime, 6)
        }



if __name__ == "__main__":
    print("=== OpenAIRealtimeClient 테스트 ===\n")
    print("이 클라이언트는 OpenAI Realtime API와 연결합니다.")
    print("실제 사용 예시는 examples/ 폴더를 참조하세요.")
    print("\n주요 기능:")
    print("- 실시간 음성 전사")
    print("- 실시간 번역")
    print("- 전사 + 번역 동시 출력")
