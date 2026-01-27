"""
로깅 유틸리티
이벤트 로깅 및 CSV/JSON 저장
"""

import logging
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# 프로젝트 설정 import
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from config.settings import TestConfig


class EventLogger:
    """이벤트 로거 클래스"""

    def __init__(self, test_name: str, service_name: str):
        """
        Args:
            test_name: 테스트 이름 (예: "test_english_to_korean_01")
            service_name: 서비스 이름 (예: "openai", "gemini")
        """
        self.test_name = test_name
        self.service_name = service_name
        self.events: List[Dict[str, Any]] = []
        self.start_time = datetime.now()

        # 결과 파일 경로
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        self.csv_path = TestConfig.RESULTS_DIR / f"{test_name}_{service_name}_{timestamp}.csv"
        self.json_path = TestConfig.RESULTS_DIR / f"{test_name}_{service_name}_{timestamp}.json"

        # 디렉토리 생성
        TestConfig.RESULTS_DIR.mkdir(exist_ok=True, parents=True)

    def log_event(self, event_type: str, content: str = "", **kwargs):
        """
        이벤트 로깅

        Args:
            event_type: 이벤트 타입 (예: "transcription", "translation", "error")
            content: 이벤트 내용 (전사 결과, 번역 결과 등)
            **kwargs: 추가 정보 (latency_ms, cost, confidence 등)
        """
        timestamp = datetime.now()
        elapsed_seconds = (timestamp - self.start_time).total_seconds()

        event = {
            'timestamp': timestamp.isoformat(),
            'elapsed_seconds': round(elapsed_seconds, 3),
            'test_name': self.test_name,
            'service': self.service_name,
            'event_type': event_type,
            'content': content,
            **kwargs
        }

        self.events.append(event)

        # 콘솔 출력
        if TestConfig.LOG_LEVEL == 'DEBUG' or event_type == 'error':
            print(f"[{elapsed_seconds:.3f}s] [{self.service_name}] {event_type}: {content[:100]}")

    def save_results(self):
        """결과를 CSV 및 JSON 파일로 저장"""
        if not self.events:
            logging.warning(f"저장할 이벤트가 없습니다: {self.test_name}")
            return

        # CSV 저장
        if TestConfig.SAVE_RESULTS_CSV:
            self._save_csv()

        # JSON 저장
        if TestConfig.SAVE_RESULTS_JSON:
            self._save_json()

        print(f"\n[Done] 결과 저장 완료:")
        print(f"   CSV: {self.csv_path}")
        print(f"   JSON: {self.json_path}")

    def _save_csv(self):
        """CSV 파일로 저장"""
        if not self.events:
            return

        # 모든 이벤트의 키 수집 (동적으로 컬럼 생성)
        all_keys = set()
        for event in self.events:
            all_keys.update(event.keys())

        fieldnames = sorted(all_keys)

        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.events)

    def _save_json(self):
        """JSON 파일로 저장"""
        summary = {
            'test_name': self.test_name,
            'service': self.service_name,
            'start_time': self.start_time.isoformat(),
            'end_time': datetime.now().isoformat(),
            'total_duration_seconds': (datetime.now() - self.start_time).total_seconds(),
            'total_events': len(self.events),
            'events': self.events
        }

        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    def get_summary(self) -> Dict[str, Any]:
        """테스트 요약 통계 반환"""
        if not self.events:
            return {}

        event_types = {}
        for event in self.events:
            et = event['event_type']
            event_types[et] = event_types.get(et, 0) + 1

        # 지연 시간 통계
        latencies = [e.get('latency_ms', 0) for e in self.events if 'latency_ms' in e]
        latency_stats = {}
        if latencies:
            latency_stats = {
                'avg': sum(latencies) / len(latencies),
                'min': min(latencies),
                'max': max(latencies),
                'count': len(latencies)
            }

        # 비용 통계
        total_cost = sum(e.get('cost', 0) for e in self.events if 'cost' in e)

        return {
            'test_name': self.test_name,
            'service': self.service_name,
            'duration_seconds': (datetime.now() - self.start_time).total_seconds(),
            'total_events': len(self.events),
            'event_types': event_types,
            'latency_stats': latency_stats,
            'total_cost_usd': round(total_cost, 4)
        }


def setup_logger(name: str, level: str = None) -> logging.Logger:
    """
    표준 Python 로거 설정

    Args:
        name: 로거 이름
        level: 로그 레벨 (기본값: TestConfig.LOG_LEVEL)

    Returns:
        설정된 로거
    """
    if level is None:
        level = TestConfig.LOG_LEVEL

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # 핸들러가 이미 있으면 중복 추가 방지
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def log_event(logger: EventLogger, event_type: str, content: str = "", **kwargs):
    """
    편의 함수: 이벤트 로깅

    Args:
        logger: EventLogger 인스턴스
        event_type: 이벤트 타입
        content: 이벤트 내용
        **kwargs: 추가 정보
    """
    logger.log_event(event_type, content, **kwargs)


if __name__ == "__main__":
    # 테스트
    print("=== EventLogger 테스트 ===\n")

    # 로거 생성
    logger = EventLogger("test_sample", "openai")

    # 이벤트 로깅
    logger.log_event("start", "테스트 시작")
    logger.log_event("transcription", "Hello, world!", latency_ms=150, confidence=0.95)
    logger.log_event("translation", "안녕하세요, 세상!", latency_ms=200, cost=0.001)
    logger.log_event("error", "Connection timeout", error_code=504)
    logger.log_event("end", "테스트 종료")

    # 요약 출력
    summary = logger.get_summary()
    print("\n테스트 요약:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    # 결과 저장
    logger.save_results()
