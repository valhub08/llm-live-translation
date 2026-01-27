"""
테스트용 오디오 파일 생성 스크립트

간단한 톤이나 노이즈를 포함한 테스트 오디오 WAV 파일을 생성합니다.
실제 음성 테스트 전에 파이프라인을 검증하는 데 사용됩니다.
"""

import wave
import math
import struct
from pathlib import Path


def generate_sine_wave(
    frequency: float,
    duration_seconds: float,
    sample_rate: int = 16000,
    amplitude: float = 0.5
) -> bytes:
    """
    사인파 오디오 생성

    Args:
        frequency: 주파수 (Hz)
        duration_seconds: 지속 시간 (초)
        sample_rate: 샘플링 레이트
        amplitude: 진폭 (0.0 ~ 1.0)

    Returns:
        bytes: PCM16 오디오 데이터
    """
    num_samples = int(sample_rate * duration_seconds)
    audio_data = []

    for i in range(num_samples):
        # 사인파 계산
        t = i / sample_rate
        sample = amplitude * math.sin(2 * math.pi * frequency * t)

        # 16-bit PCM으로 변환 (-32768 ~ 32767)
        sample_int = int(sample * 32767)
        audio_data.append(struct.pack('<h', sample_int))

    return b''.join(audio_data)


def generate_beep_sequence(
    beep_freq: float = 440,  # A4 note
    beep_duration: float = 0.5,
    pause_duration: float = 0.5,
    num_beeps: int = 3,
    sample_rate: int = 16000
) -> bytes:
    """
    비프음 시퀀스 생성 (테스트용)

    Args:
        beep_freq: 비프 주파수
        beep_duration: 각 비프 길이 (초)
        pause_duration: 비프 사이 휴지 (초)
        num_beeps: 비프 개수
        sample_rate: 샘플링 레이트

    Returns:
        bytes: PCM16 오디오 데이터
    """
    audio_parts = []

    for i in range(num_beeps):
        # 비프음
        beep = generate_sine_wave(beep_freq, beep_duration, sample_rate)
        audio_parts.append(beep)

        # 휴지 (마지막 비프 후에는 제외)
        if i < num_beeps - 1:
            pause = generate_sine_wave(0, pause_duration, sample_rate, amplitude=0)
            audio_parts.append(pause)

    return b''.join(audio_parts)


def save_wav(
    audio_data: bytes,
    output_path: Path,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2
):
    """
    WAV 파일로 저장

    Args:
        audio_data: PCM 오디오 데이터
        output_path: 출력 파일 경로
        sample_rate: 샘플링 레이트
        channels: 채널 수
        sample_width: 샘플 너비 (바이트)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(output_path), 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data)

    print(f"[Done] 생성됨: {output_path}")
    print(f"   - 샘플 레이트: {sample_rate} Hz")
    print(f"   - 채널: {channels}")
    print(f"   - 길이: {len(audio_data) / (sample_rate * channels * sample_width):.2f}초")
    print()


if __name__ == "__main__":
    import sys
    sys.path.append(str(Path(__file__).parent.parent))

    test_audio_dir = Path(__file__).parent.parent / "test_audio"

    print("=== 테스트 오디오 파일 생성 ===\n")

    # 1. 짧은 비프 시퀀스 (3초)
    print("1. 짧은 비프 시퀀스 (3초) 생성 중...")
    beep_audio = generate_beep_sequence(
        beep_freq=440,
        beep_duration=0.5,
        pause_duration=0.5,
        num_beeps=3
    )
    save_wav(beep_audio, test_audio_dir / "test_beep_3sec.wav")

    # 2. 긴 톤 (5초)
    print("2. 긴 톤 (5초) 생성 중...")
    long_tone = generate_sine_wave(frequency=440, duration_seconds=5)
    save_wav(long_tone, test_audio_dir / "test_tone_5sec.wav")

    # 3. 높은 주파수 톤 (3초)
    print("3. 높은 주파수 톤 (3초) 생성 중...")
    high_tone = generate_sine_wave(frequency=880, duration_seconds=3)
    save_wav(high_tone, test_audio_dir / "test_high_tone_3sec.wav")

    # 4. 낮은 주파수 톤 (3초)
    print("4. 낮은 주파수 톤 (3초) 생성 중...")
    low_tone = generate_sine_wave(frequency=220, duration_seconds=3)
    save_wav(low_tone, test_audio_dir / "test_low_tone_3sec.wav")

    # 5. 매우 짧은 비프 (1초) - 연결 테스트용
    print("5. 매우 짧은 비프 (1초) 생성 중...")
    short_beep = generate_beep_sequence(
        beep_freq=440,
        beep_duration=0.3,
        pause_duration=0.2,
        num_beeps=2
    )
    save_wav(short_beep, test_audio_dir / "test_quick_1sec.wav")

    print("\n=== 완료! ===")
    print(f"총 5개 파일 생성됨: {test_audio_dir}")
    print("\n사용 예시:")
    print(f"  python src/audio_input/file_streamer.py {test_audio_dir / 'test_beep_3sec.wav'}")
