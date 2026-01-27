"""
API 연결 테스트 예제

이 스크립트는 OpenAI와 Gemini API에 연결을 테스트합니다.
실제 API 키가 필요합니다.

사용법:
1. config/.env 파일에 API 키 설정
2. python examples/test_connection.py
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import APIKeys
from src.llm_clients import OpenAIRealtimeClient, GeminiLiveClient
from src.utils.logger import EventLogger


async def test_openai_connection():
    """OpenAI Realtime API 연결 테스트"""
    print("\n" + "="*60)
    print("OpenAI Realtime API 연결 테스트")
    print("="*60 + "\n")

    if not APIKeys.OPENAI_API_KEY:
        print("[Error] OPENAI_API_KEY가 설정되지 않았습니다.")
        print("   config/.env 파일을 확인하세요.")
        return False

    # 로거 생성
    logger = EventLogger("test_openai_connection", "openai")

    # 클라이언트 생성
    client = OpenAIRealtimeClient(
        api_key=APIKeys.OPENAI_API_KEY,
        mode="transcription",
        logger=logger
    )

    # 콜백 설정
    def on_transcription(text, metadata):
        print(f"📝 전사: {text}")

    def on_error(error, metadata):
        print(f"[Error] 에러: {error}")

    def on_connection_change(state):
        print(f"🔄 상태 변경: {state.value}")

    client.set_callback('transcription', on_transcription)
    client.set_callback('error', on_error)
    client.set_callback('connection_change', on_connection_change)

    try:
        # 연결 시도
        print("연결 시도 중...")
        await client.connect()

        print("[Done] 연결 성공!")
        print(f"   상태: {client.state.value}")

        # 5초 대기 (메시지 수신 테스트)
        print("\n5초 동안 연결 유지 중...")
        await asyncio.sleep(5)

        # 연결 해제
        await client.disconnect()
        print("[Done] 연결 해제 완료")

        # 결과 저장
        logger.save_results()

        return True

    except Exception as e:
        print(f"[Error] 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_gemini_connection():
    """Google Gemini Live API 연결 테스트"""
    print("\n" + "="*60)
    print("Google Gemini Live API 연결 테스트")
    print("="*60 + "\n")

    if not APIKeys.GOOGLE_API_KEY:
        print("[Error] GOOGLE_API_KEY가 설정되지 않았습니다.")
        print("   config/.env 파일을 확인하세요.")
        return False

    # 로거 생성
    logger = EventLogger("test_gemini_connection", "gemini")

    # 클라이언트 생성
    client = GeminiLiveClient(
        api_key=APIKeys.GOOGLE_API_KEY,
        mode="transcription",
        logger=logger
    )

    # 콜백 설정
    def on_transcription(text, metadata):
        print(f"📝 전사: {text}")

    def on_error(error, metadata):
        print(f"[Error] 에러: {error}")

    def on_connection_change(state):
        print(f"🔄 상태 변경: {state.value}")

    client.set_callback('transcription', on_transcription)
    client.set_callback('error', on_error)
    client.set_callback('connection_change', on_connection_change)

    try:
        # 연결 시도
        print("연결 시도 중...")
        await client.connect()

        print("[Done] 연결 성공!")
        print(f"   상태: {client.state.value}")

        # 5초 대기
        print("\n5초 동안 연결 유지 중...")
        await asyncio.sleep(5)

        # 연결 해제
        await client.disconnect()
        print("[Done] 연결 해제 완료")

        # 결과 저장
        logger.save_results()

        return True

    except Exception as e:
        print(f"[Error] 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("LLM 라이브 번역 - API 연결 테스트")
    print("="*60)

    # API 키 확인
    print("\n[API 키 확인]")
    has_openai = bool(APIKeys.OPENAI_API_KEY)
    has_gemini = bool(APIKeys.GOOGLE_API_KEY)

    print(f"OpenAI API Key: {'[Done] 설정됨' if has_openai else '[Error] 없음'}")
    print(f"Gemini API Key: {'[Done] 설정됨' if has_gemini else '[Error] 없음'}")

    if not has_openai and not has_gemini:
        print("\n[Error] API 키가 하나도 설정되지 않았습니다.")
        print("   config/.env 파일을 생성하고 API 키를 입력하세요.")
        print("\n예시:")
        print("   OPENAI_API_KEY=sk-proj-...")
        print("   GOOGLE_API_KEY=AIza...")
        return

    results = {}

    # OpenAI 테스트
    if has_openai:
        results['openai'] = await test_openai_connection()
    else:
        print("\n⚠️  OpenAI API Key가 없어 테스트를 건너뜁니다.")

    # Gemini 테스트
    if has_gemini:
        results['gemini'] = await test_gemini_connection()
    else:
        print("\n⚠️  Gemini API Key가 없어 테스트를 건너뜁니다.")

    # 결과 요약
    print("\n" + "="*60)
    print("테스트 결과 요약")
    print("="*60 + "\n")

    for service, success in results.items():
        status = "[Done] 성공" if success else "[Error] 실패"
        print(f"{service.upper():10} : {status}")

    print()


if __name__ == "__main__":
    # 이벤트 루프 실행
    asyncio.run(main())
