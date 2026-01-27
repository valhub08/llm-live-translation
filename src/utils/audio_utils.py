"""
오디오 처리 유틸리티
"""

import base64
import wave
import struct
from io import BytesIO
from typing import Optional


class AudioBuffer:
    """오디오 버퍼 관리 클래스"""

    def __init__(self, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2):
        """
        Args:
            sample_rate: 샘플레이트 (Hz)
            channels: 채널 수 (1=모노, 2=스테레오)
            sample_width: 샘플 너비 (바이트) - 2 = 16-bit
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self.buffer = bytearray()

    def append(self, audio_data: bytes):
        """오디오 데이터 추가"""
        self.buffer.extend(audio_data)

    def get_chunk(self, duration_ms: int) -> Optional[bytes]:
        """
        지정된 길이(밀리초)의 오디오 청크 가져오기

        Args:
            duration_ms: 청크 길이 (밀리초)

        Returns:
            오디오 청크 (bytes) 또는 None (버퍼가 충분하지 않은 경우)
        """
        # 필요한 바이트 수 계산
        # bytes = (sample_rate * channels * sample_width * duration_ms) / 1000
        bytes_needed = int(
            self.sample_rate * self.channels * self.sample_width * duration_ms / 1000
        )

        if len(self.buffer) < bytes_needed:
            return None

        # 청크 추출
        chunk = bytes(self.buffer[:bytes_needed])
        # 버퍼에서 제거
        self.buffer = self.buffer[bytes_needed:]

        return chunk

    def clear(self):
        """버퍼 비우기"""
        self.buffer.clear()

    def __len__(self):
        """버퍼 크기 (바이트)"""
        return len(self.buffer)

    def duration_ms(self) -> float:
        """현재 버퍼의 오디오 길이 (밀리초)"""
        if len(self.buffer) == 0:
            return 0.0

        total_samples = len(self.buffer) / (self.channels * self.sample_width)
        duration_seconds = total_samples / self.sample_rate
        return duration_seconds * 1000


def audio_to_base64(audio_data: bytes) -> str:
    """
    오디오 데이터를 Base64로 인코딩

    Args:
        audio_data: 원본 오디오 데이터 (bytes)

    Returns:
        Base64 인코딩된 문자열
    """
    return base64.b64encode(audio_data).decode('utf-8')


def base64_to_audio(b64_string: str) -> bytes:
    """
    Base64 문자열을 오디오 데이터로 디코딩

    Args:
        b64_string: Base64 인코딩된 문자열

    Returns:
        오디오 데이터 (bytes)
    """
    return base64.b64decode(b64_string)


def pcm16_to_wav(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """
    PCM16 데이터를 WAV 포맷으로 변환

    Args:
        pcm_data: PCM16 오디오 데이터
        sample_rate: 샘플레이트
        channels: 채널 수

    Returns:
        WAV 포맷 오디오 데이터
    """
    buffer = BytesIO()

    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)  # 16-bit = 2 bytes
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)

    return buffer.getvalue()


def wav_to_pcm16(wav_data: bytes) -> tuple[bytes, int, int]:
    """
    WAV 파일을 PCM16 데이터로 변환

    Args:
        wav_data: WAV 포맷 오디오 데이터

    Returns:
        (pcm_data, sample_rate, channels) 튜플
    """
    buffer = BytesIO(wav_data)

    with wave.open(buffer, 'rb') as wav_file:
        sample_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        pcm_data = wav_file.readframes(wav_file.getnframes())

    return pcm_data, sample_rate, channels


def resample_audio(
    audio_data: bytes,
    source_rate: int,
    target_rate: int,
    channels: int = 1
) -> bytes:
    """
    오디오 리샘플링 (간단한 선형 보간)

    Note: 실제 프로덕션에서는 scipy나 librosa를 사용하는 것이 좋습니다.
    이 구현은 간단한 테스트용입니다.

    Args:
        audio_data: 원본 PCM16 오디오 데이터
        source_rate: 원본 샘플레이트
        target_rate: 목표 샘플레이트
        channels: 채널 수

    Returns:
        리샘플링된 오디오 데이터
    """
    if source_rate == target_rate:
        return audio_data

    # PCM16은 2바이트씩 샘플
    samples = struct.unpack(f'<{len(audio_data)//2}h', audio_data)

    # 리샘플링 비율
    ratio = target_rate / source_rate

    # 새로운 샘플 수
    new_length = int(len(samples) * ratio)

    # 선형 보간
    resampled = []
    for i in range(new_length):
        # 원본 인덱스 (실수)
        src_index = i / ratio
        src_index_int = int(src_index)
        src_index_frac = src_index - src_index_int

        # 경계 체크
        if src_index_int >= len(samples) - 1:
            resampled.append(samples[-1])
        else:
            # 선형 보간
            sample1 = samples[src_index_int]
            sample2 = samples[src_index_int + 1]
            interpolated = sample1 + (sample2 - sample1) * src_index_frac
            resampled.append(int(interpolated))

    # 다시 바이트로 변환
    return struct.pack(f'<{len(resampled)}h', *resampled)


def convert_to_pcm16(
    audio_data: bytes,
    source_sample_width: int,
    source_channels: int,
    target_channels: int = 1
) -> bytes:
    """
    오디오를 PCM16 모노로 변환

    Args:
        audio_data: 원본 오디오 데이터
        source_sample_width: 원본 샘플 너비 (바이트)
        source_channels: 원본 채널 수
        target_channels: 목표 채널 수

    Returns:
        PCM16 오디오 데이터
    """
    # 이미 PCM16이고 채널도 같으면 그대로 반환
    if source_sample_width == 2 and source_channels == target_channels:
        return audio_data

    # 샘플 추출
    if source_sample_width == 1:  # 8-bit
        samples = struct.unpack(f'{len(audio_data)}B', audio_data)
        # 8-bit는 unsigned (0-255), 16-bit로 변환 시 center at 0
        samples = [(s - 128) * 256 for s in samples]
    elif source_sample_width == 2:  # 16-bit
        samples = struct.unpack(f'<{len(audio_data)//2}h', audio_data)
    elif source_sample_width == 3:  # 24-bit
        # 24-bit는 복잡하므로 간단히 처리
        samples = []
        for i in range(0, len(audio_data), 3):
            # 24-bit little-endian
            val = int.from_bytes(audio_data[i:i+3], 'little', signed=True)
            # 16-bit로 스케일링
            samples.append(val >> 8)
    else:
        raise ValueError(f"Unsupported sample width: {source_sample_width}")

    # 채널 변환
    if source_channels != target_channels:
        if source_channels == 2 and target_channels == 1:
            # 스테레오 → 모노: 평균
            mono_samples = []
            for i in range(0, len(samples), 2):
                if i + 1 < len(samples):
                    avg = (samples[i] + samples[i + 1]) // 2
                    mono_samples.append(avg)
            samples = mono_samples
        elif source_channels == 1 and target_channels == 2:
            # 모노 → 스테레오: 복제
            stereo_samples = []
            for s in samples:
                stereo_samples.extend([s, s])
            samples = stereo_samples

    # PCM16으로 변환
    return struct.pack(f'<{len(samples)}h', *samples)


if __name__ == "__main__":
    # 테스트
    print("=== AudioBuffer 테스트 ===\n")

    # 버퍼 생성
    buffer = AudioBuffer(sample_rate=16000, channels=1, sample_width=2)

    # 테스트 데이터 (1초 = 16000 samples * 2 bytes = 32000 bytes)
    test_audio = b'\x00\x01' * 16000  # 1초 분량

    buffer.append(test_audio)
    print(f"버퍼 크기: {len(buffer)} bytes")
    print(f"오디오 길이: {buffer.duration_ms():.1f} ms")

    # 100ms 청크 가져오기
    chunk = buffer.get_chunk(100)
    if chunk:
        print(f"청크 크기: {len(chunk)} bytes (예상: {16000 * 2 * 100 / 1000} bytes)")
        print(f"남은 버퍼: {len(buffer)} bytes")
        print(f"남은 길이: {buffer.duration_ms():.1f} ms")

    print("\n=== Base64 인코딩 테스트 ===\n")
    b64 = audio_to_base64(b'\x00\x01\x02\x03')
    print(f"Base64: {b64}")
    decoded = base64_to_audio(b64)
    print(f"Decoded: {decoded}")
    print(f"일치: {decoded == b'\\x00\\x01\\x02\\x03'}")
