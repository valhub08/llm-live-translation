"""
전사(Transcription) 테스트 스크립트

오디오 입력(마이크 또는 파일)을 LLM API로 전송하여 전사를 테스트합니다.
OpenAI Realtime API 또는 Google Gemini Live API를 사용할 수 있습니다.

사용 예시:
    # OpenAI로 파일 전사
    python examples/test_transcription.py --service openai --file test_audio/test_beep_3sec.wav

    # Gemini로 마이크 전사 (5초)
    python examples/test_transcription.py --service gemini --mic --duration 5

    # OpenAI로 실제 음성 파일 전사
    python examples/test_transcription.py --service openai --file path/to/speech.wav
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import argparse
import logging
import time

# 기본 로깅 설정
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')

sys.path.append(str(Path(__file__).parent.parent))

from src.llm_clients.openai_client import OpenAIRealtimeClient
from src.llm_clients.gemini_client import GeminiLiveClient
from src.audio_input.microphone import MicrophoneSource
from src.audio_input.file_streamer import FileStreamer
from src.utils.logger import EventLogger
from config.settings import APIKeys, AudioConfig


class TranscriptionTester:
    """전사 테스트 실행 클래스"""

    def __init__(
        self,
        service: str,
        audio_source_type: str,
        file_path: str = None,
        mode: str = "transcription",
        source_lang: str = "ko",
        target_lang: str = "en",
        duration_seconds: float = None,
        sample_rate: int = 16000
    ):
        """
        Args:
            service: 'openai' 또는 'gemini'
            audio_source_type: 'file' 또는 'mic'
            file_path: 오디오 파일 경로 (audio_source_type='file'일 때)
            duration_seconds: 캡처 시간 (초)
            sample_rate: 샘플링 레이트
        """
        self.service = service
        self.mode = mode
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.audio_source_type = audio_source_type
        self.file_path = file_path
        self.duration_seconds = duration_seconds
        self.sample_rate = sample_rate

        # LLM 클라이언트
        self.client = None
        # 오디오 소스
        self.audio_source = None
        # 로거
        self.logger = None

        # 전사 결과 저장
        self.transcriptions = []
        self.translations = []
        
        # 성능 측정용
        self.test_start_time = None
        self.first_response_time = None

    def setup(self):
        """LLM 클라이언트 및 오디오 소스 설정"""
        # 로거 생성
        test_name = f"transcription_{self.service}_{self.audio_source_type}"
        self.logger = EventLogger(test_name, self.service)

        # LLM 클라이언트 생성
        if self.service == "openai":
            # OpenAI Realtime API의 경우 24kHz 필요
            self.sample_rate = AudioConfig.OPENAI_SAMPLE_RATE

            self.client = OpenAIRealtimeClient(
                api_key=APIKeys.OPENAI_API_KEY,
                mode=self.mode,
                logger=self.logger
            )

        elif self.service == "gemini":
            # Gemini Live API의 경우 16kHz 사용
            self.sample_rate = AudioConfig.GEMINI_INPUT_SAMPLE_RATE

            self.client = GeminiLiveClient(
                api_key=APIKeys.GOOGLE_API_KEY,
                mode=self.mode,
                source_lang=self.source_lang,
                target_lang=self.target_lang,
                logger=self.logger
            )

        else:
            raise ValueError(f"Unknown service: {self.service}")

        # 콜백 설정
        self.client.set_callback('transcription', self.on_transcription)
        self.client.set_callback('translation', self.on_translation)
        self.client.set_callback('error', self.on_error)

        # 오디오 소스 생성
        if self.audio_source_type == "file":
            if not self.file_path:
                raise ValueError("File path is required for file audio source")

            self.audio_source = FileStreamer(
                file_path=self.file_path,
                sample_rate=self.sample_rate,
                chunk_size=AudioConfig.CHUNK_SIZE,
                channels=1,
                realtime_speed=True  # 실시간 속도로 스트리밍
            )

        elif self.audio_source_type == "mic":
            self.audio_source = MicrophoneSource(
                sample_rate=self.sample_rate,
                chunk_size=AudioConfig.CHUNK_SIZE,
                channels=1
            )

        else:
            raise ValueError(f"Unknown audio source type: {self.audio_source_type}")

        # 오디오 소스 콜백
        self.audio_source.set_callback('audio_chunk', self.on_audio_chunk)
        self.audio_source.set_callback('error', self.on_error)

    async def run(self):
        """테스트 실행"""
        self.audio_start_time = datetime.now()
        print(f"\n{'='*60}")
        print(f"전사 테스트 시작")
        print(f"{'='*60}")
        print(f"서비스: {self.service.upper()}")
        print(f"오디오 소스: {self.audio_source_type}")
        if self.file_path:
            print(f"파일: {self.file_path}")
        if self.duration_seconds:
            print(f"시간: {self.duration_seconds}초")
        print(f"샘플 레이트: {self.sample_rate} Hz")
        print(f"{'='*60}\n")

        try:
            # LLM 연결
            print(f"[{datetime.now().strftime('%H:%M:%S')}] LLM API 연결 중...")
            await self.client.connect()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Done] 연결 성공\n")
            self.test_start_time = time.time()

            # 오디오 캡처 및 전송 시작
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 오디오 전송 시작...")

            # 두 작업을 동시에 실행
            audio_task = asyncio.create_task(
                self.audio_source.run(duration_seconds=self.duration_seconds)
            )
            # 수신 루프가 클라이언트 내부에서 이미 실행 중인지 확인
            receive_task = None
            if hasattr(self.client, 'receive_task') and self.client.receive_task:
                receive_task = self.client.receive_task
            else:
                receive_task = asyncio.create_task(
                    self.client.receive_messages()
                )

            # 오디오 전송 완료 대기
            await audio_task

            # 오디오 전송 완료 알림
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 오디오 전송 완료")


            # 마지막 응답 받기 위해 잠시 대기
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 응답 대기 중 (5초)...")
            await asyncio.sleep(5)

            # 연결 해제
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 연결 해제 중...")
            await self.client.disconnect()

            # receive_task 취소
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass

        except Exception as e:
            print(f"\n[Error] 에러 발생: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # 결과 출력
            self.print_results()

    def _elapsed_seconds(self) -> float:
        """테스트 시작 후 경과 시간(초)"""
        if self.test_start_time is None:
            return 0.0
        return time.time() - self.test_start_time

    def on_audio_chunk(self, chunk: bytes, metadata: dict):
        """오디오 청크 수신 시 LLM으로 전송"""
        # LLM 클라이언트로 전송 (비동기)
        asyncio.create_task(self.client.send_audio(chunk))

        # 진행 상황 표시
        if metadata['chunk_index'] % 10 == 0:
            print(f"  📤 청크 {metadata['chunk_index']}: {metadata['elapsed_seconds']:.1f}초")

    def on_transcription(self, text: str, metadata: dict = None):
        """전사 결과 수신"""
        print(f"  [Speak] {text}")
        self.transcriptions.append({
            'timestamp': self._elapsed_seconds(),
            'text': text
        })

    def on_translation(self, text: str, metadata: dict = None):
        """번역 결과 수신"""
        print(f"  [Trans] {text}")
        if self.first_response_time is None:
            self.first_response_time = time.time()
        self.translations.append({
            'timestamp': self._elapsed_seconds(),
            'text': text
        })

    def on_error(self, error: Exception, context: dict):
        """에러 발생"""
        print(f"\n[Error] 에러: {error}")
        if 'location' in context:
            print(f"   위치: {context['location']}")

    def print_results(self):
        """결과 출력"""
        print(f"\n{'='*60}")
        print(f"테스트 결과")
        print(f"{'='*60}\n")

        # 전사 결과
        print(f"📝 전사 결과 ({len(self.transcriptions)}개):")
        if self.transcriptions:
            for i, trans in enumerate(self.transcriptions, 1):
                print(f"  {i}. [{trans['timestamp']}] {trans['text']}")
        else:
            print("  (전사 결과 없음)")

        # 번역 결과
        print(f"\n🌍 번역 결과 ({len(self.translations)}개):")
        if self.translations:
            for i, trans in enumerate(self.translations, 1):
                print(f"  {i}. [{trans['timestamp']}] {trans['text']}")
        else:
            print("  (번역 결과 없음)")

        # 통계
        print(f"\n📊 통계:")
        if self.audio_source:
            stats = self.audio_source.get_stats()
        # 지연 시간 분석
        latency_str = "N/A"
        if hasattr(self, 'audio_start_time') and self.transcriptions:
            # 첫 번째 전사 결과의 timestamp 찾기 (logger events에서)
            first_result_time = None
            for event in self.logger.events:
                if event['event_type'] == 'transcription':
                    first_result_time = event['timestamp']
                    break
            
            if first_result_time:
                from datetime import datetime
                t2 = datetime.fromisoformat(first_result_time)
                latency = (t2 - self.audio_start_time).total_seconds()
                latency_str = f"{latency:.2f}초"

        print(f"\n📊 통계:")
        print(f"  - 오디오 청크: {stats.get('total_chunks', 0)}개")
        print(f"  - 오디오 시간: {stats.get('total_seconds', 0):.2f}초")
        print(f"  - 총 바이트: {stats.get('total_bytes', 0):,} bytes")
        print(f"  - 첫 응답 지연: {latency_str}")

        if self.client:
            cost = self.client.get_cost_estimate()
            print(f"\n💰 예상 비용:")
            if self.service == "openai":
                print(f"  - 입력: ${cost['input_cost_usd']:.6f}")
                print(f"  - 출력: ${cost['output_cost_usd']:.6f}")
                print(f"  - 총액: ${cost['total_cost_usd']:.6f}")
            else:  # gemini
                print(f"  - 세션: ${cost.get('session_cost_usd', 0.0):.6f}")
                print(f"  - 오디오: ${cost.get('audio_cost_usd', 0.0):.6f}")
                print(f"  - 총액: ${cost.get('total_cost_usd', 0.0):.6f}")

        # 로그 저장
        if self.logger:
            self.logger.save_results()
            print(f"\n💾 로그 저장:")
            print(f"  - CSV: results/{self.logger.test_name}_{self.service}_*.csv")
            print(f"  - JSON: results/{self.logger.test_name}_{self.service}_*.json")

        print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="LLM 전사 테스트")

    parser.add_argument(
        "--service",
        choices=["openai", "gemini"],
        required=True,
        help="LLM 서비스 선택"
    )
    parser.add_argument("--mode", type=str, choices=["transcription", "translation", "both"], default="transcription", help="동작 모드")
    parser.add_argument("--src", "--source", default="ko", help="Source language code (e.g., en, ko)")
    parser.add_argument("--tgt", "--target", default="en", help="Target language code (e.g., ko, en)")

    # 오디오 소스 (배타적)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--file", type=str, help="오디오 파일 경로")
    source_group.add_argument("--mic", action="store_true", help="마이크 사용")

    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="캡처 시간 (초). 기본값: 파일 끝까지 또는 무제한"
    )

    args = parser.parse_args()

    # 오디오 소스 타입 결정
    audio_source_type = "file" if args.file else "mic"

    # API 키 확인
    APIKeys.validate()

    # 테스터 생성
    tester = TranscriptionTester(
        service=args.service,
        mode=args.mode,
        source_lang=args.src,
        target_lang=args.tgt,
        audio_source_type=audio_source_type,
        file_path=args.file,
        duration_seconds=args.duration
    )

    # 설정
    tester.setup()

    # 실행
    asyncio.run(tester.run())


if __name__ == "__main__":
    main()
