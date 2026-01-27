"""
오디오 소스 추상 기반 클래스

모든 오디오 입력 소스(마이크, 파일 등)가 구현해야 할 인터페이스를 정의합니다.
BaseLLMClient와 동일한 패턴을 따라 일관성 있는 구조를 제공합니다.
"""

import asyncio
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Callable, Dict, Any
from datetime import datetime
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from config.settings import AudioConfig


class AudioSourceState(Enum):
    """오디오 소스의 상태"""
    IDLE = "idle"           # 초기 상태
    STARTING = "starting"   # 시작 중
    ACTIVE = "active"       # 활성화 (오디오 캡처 중)
    PAUSED = "paused"       # 일시정지
    STOPPING = "stopping"   # 종료 중
    STOPPED = "stopped"     # 종료됨
    ERROR = "error"         # 에러 발생


class BaseAudioSource(ABC):
    """
    오디오 소스 추상 기반 클래스

    모든 오디오 입력 소스는 이 클래스를 상속받아 구현해야 합니다.
    마이크, 파일, 네트워크 스트림 등 다양한 소스를 동일한 인터페이스로 사용할 수 있습니다.

    주요 기능:
    - 상태 관리 (IDLE, STARTING, ACTIVE, PAUSED, STOPPING, STOPPED, ERROR)
    - 비동기 오디오 청크 생성
    - 콜백 기반 이벤트 시스템
    - 통계 추적 (총 캡처 시간, 바이트 수 등)
    """

    def __init__(
        self,
        chunk_size: int = AudioConfig.CHUNK_SIZE,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,  # 2 bytes = 16-bit
        **kwargs
    ):
        """
        Args:
            chunk_size: 한 번에 읽을 오디오 청크 크기 (바이트)
            sample_rate: 샘플링 레이트 (Hz)
            channels: 오디오 채널 수 (1=모노, 2=스테레오)
            sample_width: 샘플당 바이트 수 (2=16-bit)
            **kwargs: 추가 설정
        """
        self.chunk_size = chunk_size
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width

        # 상태
        self.state = AudioSourceState.IDLE
        self._previous_state = AudioSourceState.IDLE

        # 콜백 함수
        self.on_audio_chunk: Optional[Callable[[bytes, Dict], None]] = None
        self.on_state_change: Optional[Callable[[AudioSourceState, AudioSourceState], None]] = None
        self.on_error: Optional[Callable[[Exception, Dict], None]] = None

        # 통계
        self.stats = {
            'total_chunks': 0,
            'total_bytes': 0,
            'total_seconds': 0.0,
            'start_time': None,
            'end_time': None,
            'errors': 0,
        }

        # 제어 플래그
        self._is_running = False
        self._should_stop = False

    # ============================================================
    # 추상 메서드 - 하위 클래스에서 반드시 구현
    # ============================================================

    @abstractmethod
    async def start(self) -> None:
        """
        오디오 캡처 시작

        하위 클래스에서 구현:
        - 오디오 소스 초기화
        - 필요한 리소스 할당
        - 상태를 ACTIVE로 변경
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """
        오디오 캡처 중지

        하위 클래스에서 구현:
        - 오디오 캡처 중단
        - 리소스 정리
        - 상태를 STOPPED로 변경
        """
        pass

    @abstractmethod
    async def read_chunk(self) -> Optional[bytes]:
        """
        오디오 청크 읽기

        Returns:
            bytes: PCM 오디오 데이터 (chunk_size 바이트)
            None: 더 이상 읽을 데이터가 없음 (파일의 경우)

        하위 클래스에서 구현:
        - 오디오 소스로부터 chunk_size만큼 읽기
        - 적절한 포맷으로 변환 (필요시)
        """
        pass

    # ============================================================
    # 공통 메서드
    # ============================================================

    def set_callback(self, event_type: str, callback: Callable) -> None:
        """
        콜백 함수 설정

        Args:
            event_type: 'audio_chunk', 'state_change', 'error'
            callback: 콜백 함수
        """
        if event_type == 'audio_chunk':
            self.on_audio_chunk = callback
        elif event_type == 'state_change':
            self.on_state_change = callback
        elif event_type == 'error':
            self.on_error = callback
        else:
            raise ValueError(f"Unknown event type: {event_type}")

    async def run(self, duration_seconds: Optional[float] = None) -> None:
        """
        오디오 캡처 시작 및 실행

        Args:
            duration_seconds: 캡처할 시간 (초). None이면 무한 또는 파일 끝까지

        이 메서드는:
        1. start()를 호출하여 오디오 소스 시작
        2. 루프를 돌며 read_chunk() 호출
        3. 읽은 청크를 on_audio_chunk 콜백으로 전달
        4. duration_seconds 경과 또는 데이터 종료 시 stop() 호출
        """
        try:
            # 시작
            await self.start()
            self._is_running = True
            self._should_stop = False
            self.stats['start_time'] = datetime.now()

            start_time = asyncio.get_event_loop().time()

            # 메인 루프
            while self._is_running and not self._should_stop:
                # 시간 제한 체크
                if duration_seconds is not None:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed >= duration_seconds:
                        break

                # 청크 읽기
                chunk = await self.read_chunk()

                # 더 이상 데이터 없음 (파일 끝 등)
                if chunk is None:
                    break

                # 통계 업데이트
                self.stats['total_chunks'] += 1
                self.stats['total_bytes'] += len(chunk)
                self.stats['total_seconds'] = self.stats['total_bytes'] / (
                    self.sample_rate * self.channels * self.sample_width
                )

                # 콜백 호출
                if self.on_audio_chunk:
                    metadata = {
                        'chunk_index': self.stats['total_chunks'],
                        'chunk_size': len(chunk),
                        'elapsed_seconds': self.stats['total_seconds'],
                    }
                    self.on_audio_chunk(chunk, metadata)

        except Exception as e:
            self._emit_error(e, {'location': 'run'})
            self._change_state(AudioSourceState.ERROR)

        finally:
            # 종료
            await self.stop()
            self._is_running = False
            self.stats['end_time'] = datetime.now()

    async def pause(self) -> None:
        """일시정지"""
        if self.state == AudioSourceState.ACTIVE:
            self._change_state(AudioSourceState.PAUSED)

    async def resume(self) -> None:
        """재개"""
        if self.state == AudioSourceState.PAUSED:
            self._change_state(AudioSourceState.ACTIVE)

    def request_stop(self) -> None:
        """외부에서 중지 요청"""
        self._should_stop = True

    # ============================================================
    # 내부 헬퍼 메서드
    # ============================================================

    def _change_state(self, new_state: AudioSourceState) -> None:
        """상태 변경 및 콜백 호출"""
        old_state = self.state
        self.state = new_state

        if self.on_state_change:
            self.on_state_change(old_state, new_state)

        self._previous_state = old_state

    def _emit_error(self, exception: Exception, context: Dict[str, Any] = None) -> None:
        """에러 이벤트 발생"""
        self.stats['errors'] += 1

        if self.on_error:
            self.on_error(exception, context or {})

    # ============================================================
    # 유틸리티 메서드
    # ============================================================

    def get_stats(self) -> Dict[str, Any]:
        """통계 정보 반환"""
        stats = self.stats.copy()

        # 실제 경과 시간 계산 (벽시계 시간)
        if stats['start_time']:
            end = stats['end_time'] or datetime.now()
            stats['wall_clock_seconds'] = (end - stats['start_time']).total_seconds()

        return stats

    def get_chunk_duration_ms(self) -> float:
        """한 청크의 지속 시간 (밀리초)"""
        samples_per_chunk = self.chunk_size / self.sample_width
        duration_seconds = samples_per_chunk / self.sample_rate
        return duration_seconds * 1000

    def is_active(self) -> bool:
        """현재 활성화 상태인지 확인"""
        return self.state == AudioSourceState.ACTIVE

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"state={self.state.value}, "
            f"sample_rate={self.sample_rate}, "
            f"channels={self.channels}, "
            f"chunk_size={self.chunk_size}"
            ")"
        )


if __name__ == "__main__":
    print("=== BaseAudioSource 추상 클래스 ===\n")
    print("이 클래스는 직접 사용할 수 없습니다.")
    print("MicrophoneSource 또는 FileStreamer를 사용하세요.\n")
    print("설계 패턴:")
    print("- BaseLLMClient와 동일한 구조")
    print("- 상태 관리 (Enum)")
    print("- 콜백 기반 이벤트 시스템")
    print("- 추상 메서드 강제 (start, stop, read_chunk)")
    print("- 통계 추적")
