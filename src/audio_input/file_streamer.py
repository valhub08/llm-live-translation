"""
파일 오디오 스트리밍 모듈

오디오 파일을 실시간 속도로 스트리밍하여 마이크 입력을 시뮬레이션합니다.
테스트 및 재현 가능한 실험에 유용합니다.
"""

import asyncio
import wave
from typing import Optional
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.audio_input.base_audio_source import BaseAudioSource, AudioSourceState
from src.utils.audio_utils import resample_audio, convert_to_pcm16
from config.settings import AudioConfig


class FileStreamer(BaseAudioSource):
    """
    오디오 파일 스트리밍 클래스

    WAV 파일을 읽어 실시간 속도로 스트리밍합니다.
    마이크 입력을 시뮬레이션하므로 테스트에 적합합니다.

    Features:
    - 실시간 속도 스트리밍 (realtime_speed=True)
    - 리샘플링 지원 (파일과 다른 샘플 레이트 사용 시)
    - 자동 포맷 변환 (스테레오 → 모노, 다른 비트 뎁스 등)
    - 반복 재생 옵션 (loop=True)

    Example:
        ```python
        streamer = FileStreamer(
            file_path="test_audio/hello.wav",
            sample_rate=16000,
            realtime_speed=True
        )

        streamer.set_callback('audio_chunk', lambda chunk, meta: process(chunk))
        await streamer.run()  # 파일 끝까지
        ```
    """

    def __init__(
        self,
        file_path: str,
        chunk_size: int = AudioConfig.CHUNK_SIZE,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
        realtime_speed: bool = True,
        loop: bool = False,
        **kwargs
    ):
        """
        Args:
            file_path: WAV 파일 경로
            chunk_size: 한 번에 읽을 프레임 수
            sample_rate: 출력 샘플링 레이트 (파일과 다르면 리샘플링)
            channels: 출력 채널 수
            sample_width: 출력 샘플 너비 (바이트)
            realtime_speed: True면 실제 오디오 속도로 스트리밍 (테스트용)
            loop: True면 파일 끝에서 처음으로 반복
            **kwargs: 추가 설정
        """
        super().__init__(chunk_size, sample_rate, channels, sample_width, **kwargs)

        self.file_path = Path(file_path)
        self.realtime_speed = realtime_speed
        self.loop = loop

        # WAV 파일 객체
        self._wav_file: Optional[wave.Wave_read] = None

        # 파일 메타데이터
        self._file_sample_rate = 0
        self._file_channels = 0
        self._file_sample_width = 0
        self._file_total_frames = 0

        # 리샘플링 필요 여부
        self._needs_resampling = False
        self._needs_format_conversion = False

        # 청크 타이밍 (실시간 속도용)
        self._chunk_duration_seconds = 0.0
        self._last_chunk_time = 0.0

    async def start(self) -> None:
        """파일 열기 및 메타데이터 읽기"""
        try:
            self._change_state(AudioSourceState.STARTING)

            # 파일 존재 확인
            if not self.file_path.exists():
                raise FileNotFoundError(f"Audio file not found: {self.file_path}")

            # pydub를 사용하여 오디오 로드 (WAV, MP3 등 지원)
            from pydub import AudioSegment
            
            # 파일 확장에 따라 로드
            suffix = self.file_path.suffix.lower()
            if suffix == '.wav':
                audio = AudioSegment.from_wav(str(self.file_path))
            elif suffix == '.mp3':
                audio = AudioSegment.from_mp3(str(self.file_path))
            else:
                audio = AudioSegment.from_file(str(self.file_path))

            # 메타데이터 읽기
            self._file_channels = audio.channels
            self._file_sample_width = audio.sample_width
            self._file_sample_rate = audio.frame_rate
            self._file_total_frames = int(audio.frame_count())
            
            # 오디오 데이터를 raw PCM으로 변환
            self._audio_data = audio.get_array_of_samples().tobytes()
            self._current_pos = 0

            # 리샘플링/변환 필요 여부 체크
            self._needs_resampling = (self._file_sample_rate != self.sample_rate)
            self._needs_format_conversion = (
                self._file_channels != self.channels or
                self._file_sample_width != self.sample_width
            )

            # 청크 지속 시간 계산 (실시간 스트리밍용)
            self._chunk_duration_seconds = self.chunk_size / self.sample_rate

            self._change_state(AudioSourceState.ACTIVE)

            # 파일 정보 로그
            print(f"파일 정보:")
            print(f"  - 경로: {self.file_path}")
            print(f"  - 포맷: {suffix}")
            print(f"  - 샘플 레이트: {self._file_sample_rate} Hz → {self.sample_rate} Hz")
            print(f"  - 채널: {self._file_channels} → {self.channels}")
            print(f"  - 샘플 너비: {self._file_sample_width} bytes → {self.sample_width} bytes")
            print(f"  - 총 길이: {len(audio)/1000:.2f}초")
            print(f"  - 리샘플링: {self._needs_resampling}")

        except Exception as e:
            self._emit_error(e, {'location': 'start'})
            self._change_state(AudioSourceState.ERROR)
            raise

    async def stop(self) -> None:
        """파일 닫기"""
        try:
            self._change_state(AudioSourceState.STOPPING)
            self._audio_data = None
            self._change_state(AudioSourceState.STOPPED)
        except Exception as e:
            self._emit_error(e, {'location': 'stop'})


    async def read_chunk(self) -> Optional[bytes]:
        """
        파일에서 오디오 청크 읽기

        Returns:
            bytes: PCM 오디오 데이터
            None: 파일 끝 도달
        """
        if self._audio_data is None:
            return None

        try:
            # 실시간 속도로 재생 (필요시 대기)
            if self.realtime_speed and self._last_chunk_time > 0:
                current_time = asyncio.get_event_loop().time()
                elapsed = current_time - self._last_chunk_time
                sleep_time = self._chunk_duration_seconds - elapsed

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            # 현재 시간 기록
            if self.realtime_speed:
                self._last_chunk_time = asyncio.get_event_loop().time()

            # 바이트 읽기
            # frames = chunk_size * source_channels * source_sample_width (원래는 이랬지만 리샘플링 전후 처리 필요)
            # 여기서는 단순하게 target sample rate 기준으로 읽고 리샘플링하는 구조 유지
            
            # 리샘플링 시 읽어와야 할 원본 바이트 수 계산
            bytes_per_sample = self._file_channels * self._file_sample_width
            samples_to_read = int(self.chunk_size * (self._file_sample_rate / self.sample_rate))
            bytes_to_read = samples_to_read * bytes_per_sample

            if self._current_pos >= len(self._audio_data):
                if self.loop:
                    self._current_pos = 0
                else:
                    return None

            chunk = self._audio_data[self._current_pos : self._current_pos + bytes_to_read]
            self._current_pos += len(chunk)

            if len(chunk) == 0:
                return None

            # 포맷 변환 (필요시)
            if self._needs_format_conversion or self._needs_resampling:
                chunk = self._convert_audio(chunk)

            return chunk

        except Exception as e:
            self._emit_error(e, {'location': 'read_chunk'})
            return None

    def _convert_audio(self, audio_data: bytes) -> bytes:
        """
        오디오 포맷 변환

        Args:
            audio_data: 원본 오디오 데이터

        Returns:
            bytes: 변환된 오디오 데이터
        """
        # 1. 먼저 PCM16으로 변환 (채널 변환 포함)
        if self._needs_format_conversion:
            audio_data = convert_to_pcm16(
                audio_data,
                source_sample_width=self._file_sample_width,
                source_channels=self._file_channels,
                target_channels=self.channels
            )

        # 2. 리샘플링 (샘플 레이트 변환)
        if self._needs_resampling:
            audio_data = resample_audio(
                audio_data,
                source_rate=self._file_sample_rate,
                target_rate=self.sample_rate,
                channels=self.channels
            )

        return audio_data

    # ============================================================
    # 유틸리티 메서드
    # ============================================================

    def get_file_info(self) -> dict:
        """파일 정보 반환"""
        return {
            'file_path': str(self.file_path),
            'file_sample_rate': self._file_sample_rate,
            'file_channels': self._file_channels,
            'file_sample_width': self._file_sample_width,
            'file_total_frames': self._file_total_frames,
            'file_duration_seconds': self._file_total_frames / self._file_sample_rate if self._file_sample_rate > 0 else 0,
            'output_sample_rate': self.sample_rate,
            'output_channels': self.channels,
            'output_sample_width': self.sample_width,
            'needs_resampling': self._needs_resampling,
            'needs_format_conversion': self._needs_format_conversion,
            'realtime_speed': self.realtime_speed,
            'loop': self.loop,
        }

    def get_progress(self) -> float:
        """현재 재생 진행률 (0.0 ~ 1.0)"""
        if self._audio_data is None or len(self._audio_data) == 0:
            return 0.0

        return self._current_pos / len(self._audio_data)

    def get_remaining_seconds(self) -> float:
        """남은 재생 시간 (초)"""
        if self._audio_data is None or self._file_sample_rate == 0:
            return 0.0

        bytes_per_second = self._file_sample_rate * self._file_channels * self._file_sample_width
        remaining_bytes = len(self._audio_data) - self._current_pos
        return remaining_bytes / bytes_per_second



if __name__ == "__main__":
    import sys

    print("=== FileStreamer 테스트 ===\n")

    if len(sys.argv) < 2:
        print("사용법: python file_streamer.py <audio_file.wav>")
        sys.exit(1)

    file_path = sys.argv[1]

    async def test():
        print(f"파일 스트리밍 테스트: {file_path}\n")

        streamer = FileStreamer(
            file_path=file_path,
            sample_rate=16000,
            chunk_size=1024,
            channels=1,
            realtime_speed=True
        )

        # 콜백 설정
        def on_chunk(chunk, metadata):
            progress = streamer.get_progress()
            remaining = streamer.get_remaining_seconds()
            print(f"청크 {metadata['chunk_index']}: {len(chunk)} bytes, "
                  f"진행: {progress*100:.1f}%, 남은 시간: {remaining:.1f}s")

        def on_error(e, ctx):
            print(f"에러: {e} (위치: {ctx.get('location')})")

        streamer.set_callback('audio_chunk', on_chunk)
        streamer.set_callback('error', on_error)

        # 스트리밍 시작
        await streamer.run()

        # 통계 출력
        stats = streamer.get_stats()
        print(f"\n=== 통계 ===")
        print(f"총 청크: {stats['total_chunks']}")
        print(f"총 바이트: {stats['total_bytes']}")
        print(f"총 오디오: {stats['total_seconds']:.2f}초")
        print(f"벽시계 시간: {stats.get('wall_clock_seconds', 0):.2f}초")

        # 파일 정보
        file_info = streamer.get_file_info()
        print(f"\n=== 파일 정보 ===")
        print(f"원본 길이: {file_info['file_duration_seconds']:.2f}초")
        print(f"리샘플링: {file_info['needs_resampling']}")
        print(f"포맷 변환: {file_info['needs_format_conversion']}")

    asyncio.run(test())
