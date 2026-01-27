"""
비용 계산 유틸리티
"""

from typing import Dict, Any
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from config.settings import CostConfig


class CostCalculator:
    """API 사용 비용 계산기"""

    @staticmethod
    def calculate_openai_cost(
        audio_input_seconds: float = 0,
        audio_output_seconds: float = 0,
    ) -> Dict[str, float]:
        """
        OpenAI Realtime API 비용 계산 (추정)

        Args:
            audio_input_seconds: 오디오 입력 시간 (초)
            audio_output_seconds: 오디오 출력 시간 (초)

        Returns:
            비용 상세 정보 딕셔너리
        """
        # 1분 = 대략 6000 tokens (입력)
        input_tokens = audio_input_seconds * 100 
        output_tokens = audio_output_seconds * 200

        input_cost = (input_tokens / 1_000_000) * CostConfig.OPENAI_AUDIO_INPUT_REALTIME_PRICE
        output_cost = (output_tokens / 1_000_000) * CostConfig.OPENAI_AUDIO_OUTPUT_REALTIME_PRICE

        total_cost = input_cost + output_cost

        return {
            'service': 'openai',
            'input_seconds': round(audio_input_seconds, 2),
            'output_seconds': round(audio_output_seconds, 2),
            'input_cost_usd': round(input_cost, 6),
            'output_cost_usd': round(output_cost, 6),
            'total_cost_usd': round(total_cost, 6)
        }

    @staticmethod
    def calculate_gemini_cost(
        audio_minutes: float,
        num_sessions: int = 1
    ) -> Dict[str, float]:
        """
        Google Gemini Live API 비용 계산

        Args:
            audio_minutes: 오디오 시간 (분)
            num_sessions: 세션 수

        Returns:
            비용 상세 정보 딕셔너리
        """
        session_cost = num_sessions * CostConfig.GEMINI_SESSION_PRICE
        audio_cost = audio_minutes * CostConfig.GEMINI_MINUTE_PRICE
        total_cost = session_cost + audio_cost

        return {
            'service': 'gemini',
            'audio_minutes': audio_minutes,
            'num_sessions': num_sessions,
            'session_cost_usd': round(session_cost, 6),
            'audio_cost_usd': round(audio_cost, 6),
            'total_cost_usd': round(total_cost, 6)
        }

    @staticmethod
    def estimate_test_cost(
        duration_minutes: float,
        services: list = None
    ) -> Dict[str, Any]:
        """
        테스트 예상 비용 계산

        Args:
            duration_minutes: 총 테스트 시간 (분)
            services: 테스트할 서비스 목록 (기본값: ['openai', 'gemini'])

        Returns:
            서비스별 비용 및 총액
        """
        if services is None:
            services = ['openai', 'gemini']

        results = {}
        total_cost = 0

        if 'openai' in services:
            # 양방향 대화로 가정 (입력 = 출력)
            openai_cost = CostCalculator.calculate_openai_cost(
                audio_input_seconds=duration_minutes * 60,
                audio_output_seconds=duration_minutes * 60
            )
            results['openai'] = openai_cost
            total_cost += openai_cost['total_cost_usd']

        if 'gemini' in services:
            # 1개 세션으로 가정
            gemini_cost = CostCalculator.calculate_gemini_cost(
                audio_minutes=duration_minutes,
                num_sessions=1
            )
            results['gemini'] = gemini_cost
            total_cost += gemini_cost['total_cost_usd']

        results['total_cost_usd'] = round(total_cost, 4)
        results['duration_minutes'] = duration_minutes

        return results



def print_cost_comparison(duration_minutes: float):
    """비용 비교표 출력"""
    print(f"\n=== {duration_minutes}분 테스트 예상 비용 ===\n")

    services = ['openai', 'gemini']
    costs = CostCalculator.estimate_test_cost(duration_minutes, services)

    print(f"{'서비스':<15} {'비용 (USD)':<15} {'비고':<30}")
    print("-" * 60)

    if 'openai' in costs:
        print(f"{'OpenAI':<15} ${costs['openai']['total_cost_usd']:<14.4f} (입력+출력)")

    if 'gemini' in costs:
        print(f"{'Gemini':<15} ${costs['gemini']['total_cost_usd']:<14.4f} (세션+오디오)")

    print("-" * 60)
    print(f"{'총액':<15} ${costs['total_cost_usd']:<14.4f}")
    print()


if __name__ == "__main__":
    # 테스트
    print("=== CostCalculator 테스트 ===\n")

    # 1분 테스트
    print_cost_comparison(1)

    # 5분 테스트
    print_cost_comparison(5)

    # 1시간 테스트
    print_cost_comparison(60)

    # 실제 프로젝트 예상 비용
    print("\n=== 프로젝트 전체 예상 비용 ===\n")

    # 기본 테스트: 5분 × 10개 = 50분
    basic_tests = CostCalculator.estimate_test_cost(50, ['openai', 'gemini'])
    print(f"기본 테스트 (50분): ${basic_tests['total_cost_usd']:.2f}")

    # 긴 세션 테스트: 1시간 × 3개 = 180분
    long_tests = CostCalculator.estimate_test_cost(180, ['openai', 'gemini'])
    print(f"긴 세션 테스트 (180분): ${long_tests['total_cost_usd']:.2f}")

    # 총액
    total = basic_tests['total_cost_usd'] + long_tests['total_cost_usd']
    print(f"\n총 예상 비용: ${total:.2f}")
    print(f"여유 포함 (20%): ${total * 1.2:.2f}")
