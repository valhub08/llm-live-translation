"""
번역(Translation) 테스트 스크립트

오디오 입력(마이크 또는 파일)을 LLM API로 전송하여 번역을 테스트합니다.
예: 영어 음성 → 한국어 텍스트

사용 예시:
    # OpenAI로 파일 번역 (영어 → 한국어)
    python examples/test_translation.py --service openai --file path/to/english.wav --source en --target ko

    # Gemini로 마이크 번역 (한국어 → 영어, 10초)
    python examples/test_translation.py --service gemini --mic --source ko --target en --duration 10
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import argparse

sys.path.append(str(Path(__file__).parent.parent))

from src.llm_clients.openai_client import OpenAIRealtimeClient
from src.llm_clients.gemini_client import GeminiLiveClient
from src.audio_input.microphone import MicrophoneSource
from src.audio_input.file_streamer import FileStreamer
from src.utils.logger import EventLogger
from config.settings import APIKeys, AudioConfig


class TranslationTester:
    """번역 테스트 실행 클래스"""

    def __init__(
        self,
        service: str,
        audio_source_type: str,
        source_lang: str,
        target_lang: str,
        file_path: str = None,
        duration_seconds: float = None,
        sample_rate: int = 16000
    ):
        """
        Args:
            service: 'openai' 또는 'gemini'
            audio_source_type: 'file' 또는 'mic'
            source_lang: 소스 언어 (예: 'en', 'ko')
            target_lang: 타겟 언어 (예: 'ko', 'en')
            file_path: 오디오 파일 경로
            duration_seconds: 캡처 시간 (초)
            sample_rate: 샘플링 레이트
        """
        self.service = service
        self.audio_source_type = audio_source_type
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.file_path = file_path
        self.duration_seconds = duration_seconds
        self.sample_rate = sample_rate

        # LLM 클라이언트
        self.client = None
        # 오디오 소스
        self.audio_source = None
        # 로거
        self.logger = None

        # 전사 및 번역 결과 저장
        self.transcriptions = []
        self.translations = []

    def setup(self):
        """LLM 클라이언트 및 오디오 소스 설정"""
        # 로거 생성
        test_name = f"translation_{self.service}_{self.audio_source_type}_{self.source_lang}_to_{self.target_lang}"
        self.logger = EventLogger(test_name, self.service)

        # LLM 클라이언트 생성
        if self.service == "openai":
            self.sample_rate = AudioConfig.OPENAI_SAMPLE_RATE

            self.client = OpenAIRealtimeClient(
                api_key=APIKeys.OPENAI_API_KEY,
                mode="translation",  # 번역 모드
                source_lang=self.source_lang,
                target_lang=self.target_lang,
                logger=self.logger
            )

        elif self.service == "gemini":
            self.sample_rate = AudioConfig.GEMINI_INPUT_SAMPLE_RATE

            self.client = GeminiLiveClient(
                api_key=APIKeys.GOOGLE_API_KEY,
                mode="translation",  # 번역 모드
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
                realtime_speed=True
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
        print(f"\n{'='*60}")
        print(f"번역 테스트 시작")
        print(f"{'='*60}")
        print(f"서비스: {self.service.upper()}")
        print(f"오디오 소스: {self.audio_source_type}")
        print(f"번역: {self.source_lang.upper()} → {self.target_lang.upper()}")
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

            # 오디오 캡처 및 전송 시작
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 오디오 전송 시작...")

            # 두 작업을 동시에 실행
            audio_task = asyncio.create_task(
                self.audio_source.run(duration_seconds=self.duration_seconds)
            )
            receive_task = asyncio.create_task(
                self.client.receive_messages()
            )

            # 오디오 전송 완료 대기
            await audio_task

            # 오디오 전송 완료 알림
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 오디오 전송 완료")

            # 마지막 응답 받기 위해 잠시 대기
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 응답 대기 중 (2초)...")
            await asyncio.sleep(2)

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

    def on_audio_chunk(self, chunk: bytes, metadata: dict):
        """오디오 청크 수신 시 LLM으로 전송"""
        # LLM 클라이언트로 전송 (비동기)
        asyncio.create_task(self.client.send_audio(chunk))

        # 진행 상황 표시
        if metadata['chunk_index'] % 10 == 0:
            print(f"  📤 청크 {metadata['chunk_index']}: {metadata['elapsed_seconds']:.1f}초")

    def on_transcription(self, text: str, metadata: dict):
        """원본 전사 결과 수신 (선택적)"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"\n[{timestamp}] 🔤 원본: {text}")

        self.transcriptions.append({
            'timestamp': timestamp,
            'text': text,
            'metadata': metadata
        })

    def on_translation(self, text: str, metadata: dict):
        """번역 결과 수신"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"\n[{timestamp}] 🌐 번역: {text}")

        self.translations.append({
            'timestamp': timestamp,
            'text': text,
            'metadata': metadata
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

        # 원본 전사 결과
        if self.transcriptions:
            print(f"🔤 원본 전사 ({len(self.transcriptions)}개):")
            for i, trans in enumerate(self.transcriptions, 1):
                print(f"  {i}. [{trans['timestamp']}] {trans['text']}")
            print()

        # 번역 결과
        print(f"🌐 번역 결과 ({len(self.translations)}개):")
        if self.translations:
            for i, trans in enumerate(self.translations, 1):
                print(f"  {i}. [{trans['timestamp']}] {trans['text']}")
        else:
            print("  (번역 결과 없음)")

        # 통계
        print(f"\n📊 통계:")
        if self.audio_source:
            stats = self.audio_source.get_stats()
            print(f"  - 오디오 청크: {stats['total_chunks']}개")
            print(f"  - 오디오 시간: {stats['total_seconds']:.2f}초")
            print(f"  - 총 바이트: {stats['total_bytes']:,} bytes")

        if self.client:
            cost = self.client.get_cost_estimate()
            print(f"\n💰 예상 비용:")
            if self.service == "openai":
                print(f"  - 입력: ${cost['input_cost_usd']:.6f}")
                print(f"  - 출력: ${cost['output_cost_usd']:.6f}")
                print(f"  - 총액: ${cost['total_cost_usd']:.6f}")
            else:  # gemini
                print(f"  - 세션: ${cost['session_cost_usd']:.6f}")
                print(f"  - 오디오: ${cost['audio_cost_usd']:.6f}")
                print(f"  - 총액: ${cost['total_cost_usd']:.6f}")

        # 로그 저장
        if self.logger:
            self.logger.save_results()
            print(f"\n💾 로그 저장:")
            print(f"  - CSV: results/{self.logger.test_name}_{self.service}_*.csv")
            print(f"  - JSON: results/{self.logger.test_name}_{self.service}_*.json")

        print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="LLM 번역 테스트")

    parser.add_argument(
        "--service",
        choices=["openai", "gemini"],
        required=True,
        help="LLM 서비스 선택"
    )

    # 오디오 소스 (배타적)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--file", type=str, help="오디오 파일 경로")
    source_group.add_argument("--mic", action="store_true", help="마이크 사용")

    parser.add_argument(
        "--source",
        type=str,
        default="en",
        help="소스 언어 (기본: en)"
    )

    parser.add_argument(
        "--target",
        type=str,
        default="ko",
        help="타겟 언어 (기본: ko)"
    )

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
    tester = TranslationTester(
        service=args.service,
        audio_source_type=audio_source_type,
        source_lang=args.source,
        target_lang=args.target,
        file_path=args.file,
        duration_seconds=args.duration
    )

    # 설정
    tester.setup()

    # 실행
    asyncio.run(tester.run())


if __name__ == "__main__":
    main()
