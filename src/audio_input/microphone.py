"""
마이크 오디오 캡처 모듈

실시간으로 마이크에서 오디오를 캡처하여 스트림으로 제공합니다.
BaseAudioSource를 구현합니다.
"""

import asyncio
import pyaudio
from typing import Optional, Dict, Any
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.audio_input.base_audio_source import BaseAudioSource, AudioSourceState
from config.settings import AudioConfig


class MicrophoneSource(BaseAudioSource):
    """
    마이크 오디오 캡처 클래스

    시스템 마이크에서 실시간으로 오디오를 캡처합니다.
    PyAudio를 사용하여 마이크 입력을 받아옵니다.

    Example:
        ```python
        mic = MicrophoneSource(
            sample_rate=16000,
            chunk_size=1024,
            device_index=None  # 기본 마이크
        )

        mic.set_callback('audio_chunk', lambda chunk, meta: print(f"Got {len(chunk)} bytes"))
        mic.set_callback('error', lambda e, ctx: print(f"Error: {e}"))

        await mic.run(duration_seconds=10)  # 10초간 캡처
        ```
    """

    def __init__(
        self,
        chunk_size: int = AudioConfig.CHUNK_SIZE,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
        device_index: Optional[int] = None,
        **kwargs
    ):
        """
        Args:
            chunk_size: 한 번에 읽을 프레임 수
            sample_rate: 샘플링 레이트 (Hz)
            channels: 채널 수 (1=모노, 2=스테레오)
            sample_width: 샘플당 바이트 수 (2=16-bit)
            device_index: 마이크 장치 인덱스 (None=기본 마이크)
            **kwargs: 추가 설정
        """
        super().__init__(chunk_size, sample_rate, channels, sample_width, **kwargs)

        self.device_index = device_index

        # PyAudio 객체
        self._pyaudio: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None

        # 오디오 포맷 (PyAudio)
        self._format = pyaudio.paInt16  # 16-bit

    async def start(self) -> None:
        """마이크 캡처 시작"""
        try:
            self._change_state(AudioSourceState.STARTING)

            # PyAudio 초기화
            self._pyaudio = pyaudio.PyAudio()

            # 스트림 열기
            self._stream = self._pyaudio.open(
                format=self._format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=None  # 동기 모드 사용
            )

            self._change_state(AudioSourceState.ACTIVE)

        except Exception as e:
            self._emit_error(e, {'location': 'start'})
            self._change_state(AudioSourceState.ERROR)
            raise

    async def stop(self) -> None:
        """마이크 캡처 중지"""
        try:
            self._change_state(AudioSourceState.STOPPING)

            # 스트림 닫기
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None

            # PyAudio 종료
            if self._pyaudio:
                self._pyaudio.terminate()
                self._pyaudio = None

            self._change_state(AudioSourceState.STOPPED)

        except Exception as e:
            self._emit_error(e, {'location': 'stop'})

    async def read_chunk(self) -> Optional[bytes]:
        """
        마이크에서 오디오 청크 읽기

        Returns:
            bytes: PCM 오디오 데이터
            None: 에러 발생 시
        """
        if not self._stream or not self._stream.is_active():
            return None

        try:
            # PyAudio는 동기 블로킹 I/O이므로 asyncio executor에서 실행
            loop = asyncio.get_event_loop()
            audio_data = await loop.run_in_executor(
                None,
                self._stream.read,
                self.chunk_size,
                False  # exception_on_overflow=False
            )

            return audio_data

        except IOError as e:
            # 오버플로우 등 일시적 에러는 무시
            if e.errno == pyaudio.paInputOverflowed:
                # 경고만 출력하고 계속 진행
                return b'\x00' * (self.chunk_size * self.sample_width * self.channels)
            else:
                self._emit_error(e, {'location': 'read_chunk'})
                return None

        except Exception as e:
            self._emit_error(e, {'location': 'read_chunk'})
            return None

    # ============================================================
    # 유틸리티 메서드
    # ============================================================

    @staticmethod
    def list_devices() -> None:
        """사용 가능한 오디오 장치 목록 출력"""
        p = pyaudio.PyAudio()
        print("=== 사용 가능한 오디오 입력 장치 ===\n")

        for i in range(p.get_device_count()):
            device_info = p.get_device_info_by_index(i)

            # 입력 채널이 있는 장치만 출력
            if device_info['maxInputChannels'] > 0:
                print(f"[{i}] {device_info['name']}")
                print(f"    - 입력 채널: {device_info['maxInputChannels']}")
                print(f"    - 샘플 레이트: {int(device_info['defaultSampleRate'])} Hz")
                print()

        p.terminate()

    def get_device_info(self) -> Optional[Dict[str, Any]]:
        """현재 사용 중인 마이크 장치 정보 반환"""
        if not self._pyaudio:
            return None

        try:
            if self.device_index is not None:
                return self._pyaudio.get_device_info_by_index(self.device_index)
            else:
                return self._pyaudio.get_default_input_device_info()
        except Exception:
            return None


if __name__ == "__main__":
    import sys

    print("=== MicrophoneSource 테스트 ===\n")

    # 사용 가능한 장치 목록
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        MicrophoneSource.list_devices()
        sys.exit(0)

    # 간단한 테스트
    async def test():
        print("3초간 마이크 캡처 테스트...\n")

        mic = MicrophoneSource(
            sample_rate=16000,
            chunk_size=1024,
            channels=1
        )

        # 콜백 설정
        def on_chunk(chunk, metadata):
            print(f"청크 {metadata['chunk_index']}: {len(chunk)} bytes, "
                  f"경과 시간: {metadata['elapsed_seconds']:.2f}s")

        def on_error(e, ctx):
            print(f"에러: {e} (위치: {ctx.get('location')})")

        mic.set_callback('audio_chunk', on_chunk)
        mic.set_callback('error', on_error)

        # 3초간 캡처
        await mic.run(duration_seconds=3)

        # 통계 출력
        stats = mic.get_stats()
        print(f"\n=== 통계 ===")
        print(f"총 청크: {stats['total_chunks']}")
        print(f"총 바이트: {stats['total_bytes']}")
        print(f"총 오디오: {stats['total_seconds']:.2f}초")
        print(f"벽시계 시간: {stats.get('wall_clock_seconds', 0):.2f}초")

    asyncio.run(test())
