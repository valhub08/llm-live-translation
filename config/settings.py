"""
프로젝트 설정 파일
API 키 로드 및 전역 설정 관리
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트 디렉토리
PROJECT_ROOT = Path(__file__).parent.parent

# .env 파일 로드
load_dotenv(PROJECT_ROOT / 'config' / '.env')

# API Keys
# API Keys
class APIKeys:
    """API 키 관리 클래스"""
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')

    @classmethod
    def validate(cls):
        """필수 API 키가 설정되어 있는지 확인"""
        missing_keys = []
        if not cls.OPENAI_API_KEY:
            missing_keys.append('OPENAI_API_KEY')
        if not cls.GOOGLE_API_KEY:
            missing_keys.append('GOOGLE_API_KEY')

        if missing_keys:
            print(f"⚠️  경고: 다음 API 키가 설정되지 않았습니다: {', '.join(missing_keys)}")
            print(f"   config/.env 파일을 확인해주세요.")
            return False

        print("[Done] 모든 필수 API 키가 설정되었습니다.")
        return True


# API 엔드포인트
class APIEndpoints:
    """API 엔드포인트 URL"""
    OPENAI_REALTIME = "wss://api.openai.com/v1/realtime"
    GOOGLE_GEMINI_LIVE = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"


# 오디오 설정
class AudioConfig:
    """오디오 입출력 설정"""
    # OpenAI 권장 설정
    OPENAI_SAMPLE_RATE = 24000  # Hz
    OPENAI_CHANNELS = 1  # Mono
    OPENAI_SAMPLE_WIDTH = 2  # 16-bit
    OPENAI_FORMAT = "pcm16"

    # Google Gemini 권장 설정
    GEMINI_INPUT_SAMPLE_RATE = 16000  # Hz
    GEMINI_OUTPUT_SAMPLE_RATE = 24000  # Hz
    GEMINI_CHANNELS = 1  # Mono
    GEMINI_SAMPLE_WIDTH = 2  # 16-bit
    GEMINI_CHUNK_SIZE = 1024  # bytes

    # 공통 설정 (기본값)
    DEFAULT_SAMPLE_RATE = 16000
    DEFAULT_CHANNELS = 1
    DEFAULT_CHUNK_DURATION_MS = 100  # 100ms per chunk
    CHUNK_SIZE = 1024  # 기본 청크 크기 (프레임 수)


# 테스트 설정
class TestConfig:
    """테스트 관련 설정"""
    # 디렉토리
    TEST_AUDIO_DIR = PROJECT_ROOT / 'test_audio'
    GROUND_TRUTH_DIR = PROJECT_ROOT / 'ground_truth'
    RESULTS_DIR = PROJECT_ROOT / 'results'

    # 테스트 모드
    USE_MICROPHONE = False  # False면 파일 모드

    # 로깅
    LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
    SAVE_RESULTS_CSV = True
    SAVE_RESULTS_JSON = True

    # 성능 측정
    MEASURE_LATENCY = True
    MEASURE_COST = True


# 비용 계산 (토큰당 가격)
class CostConfig:
    """API 비용 계산을 위한 설정"""
    # OpenAI Realtime (gpt-realtime)
    OPENAI_AUDIO_INPUT_PRICE = 0.06 / 1_000_000  # $0.06 per 1M tokens (텍스트 기준, 실제 오디오는 더 비쌈)
    # 실제 오디오: $100 / 1M tokens (입력), $200 / 1M tokens (출력) -> GPT-4o Realtime 공식 가격 확인
    OPENAI_AUDIO_INPUT_REALTIME_PRICE = 100 / 1_000_000
    OPENAI_AUDIO_OUTPUT_REALTIME_PRICE = 200 / 1_000_000

    # OpenAI 토큰 계산: 입력 1 token = 대략적인 분량
    # 1분 오디오 = 6000 tokens (입력), 12000 tokens (출력) - 대략적 추정

    # Google Gemini Live
    GEMINI_SESSION_PRICE = 0.0  # 현재 프리뷰 무료 티어 가능성 있음
    GEMINI_MINUTE_PRICE = 0.002  # $0.002 per minute for flash



# 프롬프트 템플릿
class PromptTemplates:
    """각 서비스별 프롬프트 템플릿"""

    # OpenAI Realtime - 전사 전용
    OPENAI_TRANSCRIPTION_ONLY = """
You are a transcription assistant. Your ONLY task is to transcribe the audio you hear.

RULES:
1. DO NOT respond or engage in conversation
2. DO NOT ask questions
3. DO NOT provide explanations
4. ONLY output the exact words spoken
5. Output format: Plain text transcription only

Begin transcription:
"""

    # OpenAI Realtime - 번역 전용
    OPENAI_TRANSLATION_ONLY = """
You are a translation assistant. Your ONLY task is to translate the audio you hear from {source_lang} to {target_lang}.

RULES:
1. DO NOT respond or engage in conversation
2. DO NOT ask questions
3. DO NOT provide explanations
4. ONLY output the translation
5. Output format: Translated text only in {target_lang}

Begin translation:
"""

    OPENAI_TRANSCRIPTION_AND_TRANSLATION = """
You are a live transcription and translation assistant.
The speaker is speaking in {source_lang}.

For EVERY utterance you hear:
1. Transcribe the spoken text in {source_lang} exactly. Prefix it with [ORIGINAL].
2. Translate that text into {target_lang}. Prefix it with [TRANSLATION].

FORMAT:
[ORIGINAL] <spoken text in {source_lang}>
[TRANSLATION] <translated text in {target_lang}>

CRITICAL: 
- The input is ALWAYS in {source_lang}. Do not assume it is English.
- Do not add any other text or explanations.
"""

    # Google Gemini Live - 전사 전용
    GEMINI_TRANSCRIPTION_ONLY = """
You are a transcription system. Transcribe exactly what you hear.
Do not respond. Do not explain. Output only the spoken words.
"""

    # Google Gemini Live - 번역 전용
    GEMINI_TRANSLATION_ONLY = """
You are a live translation system. Your ONLY task is to translate everything I say into {target_lang}.
Output ONLY the translated words. Do not respond to me, do not ask questions, and do not explain.
Immediately speak the translation in {target_lang}.
"""

    # Google Gemini Live - 전사 + 번역 (Both)
    GEMINI_TRANSCRIPTION_AND_TRANSLATION = """
You are a live translation system. Your task is to translate everything I say into {target_lang}.
Output ONLY the translation. Do not repeat me, do not explain, and do not engage in conversation.
Immediately speak the translation in {target_lang}.
"""


# 지원 언어
class LanguageConfig:
    """지원 언어 설정"""
    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'ko': 'Korean',
        'ja': 'Japanese',
        'zh': 'Chinese',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese'
    }

    # 기본 언어 쌍
    DEFAULT_SOURCE_LANG = 'en'
    DEFAULT_TARGET_LANG = 'ko'


# 개발 모드 설정
DEBUG_MODE = os.getenv('DEBUG', 'false').lower() == 'true'

if __name__ == "__main__":
    # 설정 테스트
    print("=== LLM Live Translation - 설정 확인 ===\n")

    print(f"프로젝트 루트: {PROJECT_ROOT}")
    print(f"디버그 모드: {DEBUG_MODE}\n")

    print("API 키 확인:")
    APIKeys.validate()
    print()

    print("API 엔드포인트:")
    print(f"  OpenAI: {APIEndpoints.OPENAI_REALTIME}")
    print(f"  Gemini: {APIEndpoints.GOOGLE_GEMINI_LIVE[:50]}...")
    print()

    print("오디오 설정:")
    print(f"  OpenAI: {AudioConfig.OPENAI_SAMPLE_RATE}Hz, {AudioConfig.OPENAI_CHANNELS}ch")
    print(f"  Gemini: {AudioConfig.GEMINI_INPUT_SAMPLE_RATE}Hz, {AudioConfig.GEMINI_CHANNELS}ch")
    print()

    print("테스트 디렉토리:")
    print(f"  오디오: {TestConfig.TEST_AUDIO_DIR}")
    print(f"  결과: {TestConfig.RESULTS_DIR}")
    print()

    print("비용 설정:")
    print(f"  OpenAI: ${AudioConfig.OPENAI_SAMPLE_RATE * CostConfig.OPENAI_INPUT_TOKENS_PER_SECOND * CostConfig.OPENAI_AUDIO_INPUT_PRICE * 60:.4f}/분 (입력)")
    print(f"  Gemini: ${CostConfig.GEMINI_MINUTE_PRICE}/분")
