"""
LLM API 클라이언트 기본 추상 클래스
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Callable, Dict, Any
import asyncio
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.utils.logger import EventLogger


class ClientState(Enum):
    """클라이언트 상태"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    LISTENING = "listening"
    ERROR = "error"
    CLOSED = "closed"


class BaseLLMClient(ABC):
    """
    LLM API 클라이언트 기본 클래스

    모든 LLM 클라이언트(OpenAI, Gemini 등)는 이 클래스를 상속받아 구현
    """

    def __init__(
        self,
        api_key: str,
        logger: Optional[EventLogger] = None,
        **kwargs
    ):
        """
        Args:
            api_key: API 키
            logger: EventLogger 인스턴스 (없으면 로깅 안 함)
            **kwargs: 추가 설정
        """
        self.api_key = api_key
        self.logger = logger
        self.state = ClientState.DISCONNECTED
        self.config = kwargs

        # 콜백 함수들
        self.on_transcription: Optional[Callable[[str, Dict], None]] = None
        self.on_translation: Optional[Callable[[str, Dict], None]] = None
        self.on_error: Optional[Callable[[Exception, Dict], None]] = None
        self.on_connection_change: Optional[Callable[[ClientState], None]] = None

        # WebSocket 연결
        self.ws = None

        # 통계
        self.stats = {
            'total_audio_sent_seconds': 0,
            'total_audio_received_seconds': 0,
            'total_text_received': 0,
            'total_errors': 0,
            'connection_time': None,
            'disconnection_time': None
        }

    @abstractmethod
    async def connect(self, **kwargs):
        """
        API 서버에 연결

        서브클래스에서 구현 필요
        """
        pass

    @abstractmethod
    async def disconnect(self):
        """
        API 서버 연결 해제

        서브클래스에서 구현 필요
        """
        pass

    @abstractmethod
    async def send_audio(self, audio_data: bytes):
        """
        오디오 데이터 전송

        Args:
            audio_data: PCM16 오디오 데이터

        서브클래스에서 구현 필요
        """
        pass

    @abstractmethod
    async def receive_messages(self):
        """
        메시지 수신 루프

        서브클래스에서 구현 필요
        """
        pass

    def set_callback(self, event_type: str, callback: Callable):
        """
        이벤트 콜백 설정

        Args:
            event_type: 이벤트 타입 ('transcription', 'translation', 'error', 'connection_change')
            callback: 콜백 함수
        """
        if event_type == 'transcription':
            self.on_transcription = callback
        elif event_type == 'translation':
            self.on_translation = callback
        elif event_type == 'error':
            self.on_error = callback
        elif event_type == 'connection_change':
            self.on_connection_change = callback
        else:
            raise ValueError(f"Unknown event type: {event_type}")

    def _change_state(self, new_state: ClientState):
        """상태 변경 및 콜백 호출"""
        old_state = self.state
        self.state = new_state

        if self.logger:
            self.logger.log_event(
                "state_change",
                f"{old_state.value} -> {new_state.value}"
            )

        if self.on_connection_change:
            self.on_connection_change(new_state)

    def _log(self, event_type: str, content: str = "", **kwargs):
        """로깅 헬퍼 함수"""
        if self.logger:
            self.logger.log_event(event_type, content, **kwargs)

    def _emit_transcription(self, text: str, metadata: Dict[str, Any] = None):
        """전사 결과 콜백 호출"""
        if metadata is None:
            metadata = {}

        self._log("transcription", text, **metadata)

        if self.on_transcription:
            self.on_transcription(text, metadata)

    def _emit_translation(self, text: str, metadata: Dict[str, Any] = None):
        """번역 결과 콜백 호출"""
        if metadata is None:
            metadata = {}

        self._log("translation", text, **metadata)

        if self.on_translation:
            self.on_translation(text, metadata)

    def _emit_error(self, error: Exception, metadata: Dict[str, Any] = None):
        """에러 콜백 호출"""
        if metadata is None:
            metadata = {}

        self.stats['total_errors'] += 1
        self._log("error", str(error), **metadata)

        if self.on_error:
            self.on_error(error, metadata)

    async def run(
        self,
        audio_source: asyncio.Queue,
        duration_seconds: Optional[float] = None
    ):
        """
        클라이언트 실행 (연결 + 송수신)

        Args:
            audio_source: 오디오 데이터를 제공하는 asyncio.Queue
            duration_seconds: 실행 시간 (초), None이면 무제한
        """
        try:
            # 연결
            await self.connect()

            # 송수신 태스크 시작
            receive_task = asyncio.create_task(self.receive_messages())
            send_task = asyncio.create_task(self._send_audio_loop(audio_source))

            # duration_seconds 동안만 실행
            if duration_seconds:
                await asyncio.sleep(duration_seconds)
                send_task.cancel()
                receive_task.cancel()
            else:
                # 둘 중 하나라도 종료되면 종료
                done, pending = await asyncio.wait(
                    [receive_task, send_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                # 나머지 취소
                for task in pending:
                    task.cancel()

        except Exception as e:
            self._emit_error(e, {"location": "run"})
            raise
        finally:
            await self.disconnect()

    async def _send_audio_loop(self, audio_source: asyncio.Queue):
        """오디오 전송 루프"""
        try:
            while True:
                audio_data = await audio_source.get()

                if audio_data is None:  # 종료 신호
                    break

                await self.send_audio(audio_data)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._emit_error(e, {"location": "_send_audio_loop"})

    def get_stats(self) -> Dict[str, Any]:
        """통계 정보 반환"""
        return self.stats.copy()


if __name__ == "__main__":
    print("=== BaseLLMClient 테스트 ===\n")
    print("이 클래스는 추상 클래스입니다.")
    print("OpenAIRealtimeClient 또는 GeminiLiveClient를 사용하세요.")
