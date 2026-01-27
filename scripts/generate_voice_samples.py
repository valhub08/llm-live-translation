"""
실제 음성 샘플 생성 스크립트

TTS를 사용하여 테스트용 음성 파일을 생성합니다.
- Google TTS (gTTS): 무료, 다양한 언어 지원
- OpenAI TTS: 고품질, API 비용 발생

각 샘플은 Ground Truth 전사본/번역본과 함께 저장됩니다.
"""

from gtts import gTTS
from pathlib import Path
import json
import sys
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))
from config.settings import APIKeys

# 테스트 문장 정의
# 각 문장은 5-10초 길이로 설계
TEST_SENTENCES = {
    "en_short": {
        "text": "Hello, how are you today?",
        "lang": "en",
        "duration_estimate": "2-3초",
        "translation_ko": "안녕하세요, 오늘 어떻게 지내세요?"
    },
    "en_medium": {
        "text": "The weather is beautiful today. I think it's a perfect day for a walk in the park.",
        "lang": "en",
        "duration_estimate": "5-7초",
        "translation_ko": "오늘 날씨가 아름답네요. 공원에서 산책하기 완벽한 날인 것 같아요."
    },
    "en_long": {
        "text": "Artificial intelligence is transforming the way we live and work. From voice assistants to self-driving cars, AI technologies are becoming an integral part of our daily lives.",
        "lang": "en",
        "duration_estimate": "10-12초",
        "translation_ko": "인공지능은 우리가 살고 일하는 방식을 변화시키고 있습니다. 음성 비서부터 자율주행차까지, AI 기술은 우리 일상생활의 필수적인 부분이 되어가고 있습니다."
    },
    "en_technical": {
        "text": "Machine learning models require large amounts of training data to achieve high accuracy. The quality of data is just as important as the quantity.",
        "lang": "en",
        "duration_estimate": "8-10초",
        "translation_ko": "머신러닝 모델은 높은 정확도를 달성하기 위해 많은 양의 훈련 데이터가 필요합니다. 데이터의 품질은 양만큼이나 중요합니다."
    },
    "ko_short": {
        "text": "안녕하세요, 만나서 반갑습니다.",
        "lang": "ko",
        "duration_estimate": "2-3초",
        "translation_en": "Hello, nice to meet you."
    },
    "ko_medium": {
        "text": "저는 오늘 새로운 프로젝트를 시작했습니다. 매우 흥미롭고 도전적인 작업이에요.",
        "lang": "ko",
        "duration_estimate": "5-7초",
        "translation_en": "I started a new project today. It's a very interesting and challenging task."
    },
    "ko_long": {
        "text": "인공지능 기술의 발전은 우리 사회에 많은 변화를 가져오고 있습니다. 특히 번역 기술의 발전으로 언어의 장벽이 점점 낮아지고 있습니다.",
        "lang": "ko",
        "duration_estimate": "10-12초",
        "translation_en": "The advancement of artificial intelligence technology is bringing many changes to our society. Especially, the development of translation technology is gradually lowering language barriers."
    }
}


def generate_gtts_sample(sentence_id: str, data: dict, output_dir: Path):
    """
    Google TTS로 음성 샘플 생성

    Args:
        sentence_id: 문장 ID (예: 'en_short')
        data: 문장 데이터 (text, lang, translation 등)
        output_dir: 출력 디렉토리
    """
    text = data['text']
    lang = data['lang']

    # 파일명
    filename = f"{sentence_id}_gtts.mp3"
    output_path = output_dir / filename

    print(f"생성 중: {filename}")
    print(f"  텍스트: {text}")
    print(f"  언어: {lang}")

    try:
        # gTTS 생성
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(str(output_path))

        print(f"  [Done] 생성 완료: {output_path}")
        return str(output_path)

    except Exception as e:
        print(f"  [Error] 에러: {e}")
        return None


def convert_mp3_to_wav(mp3_path: Path, sample_rate: int = 16000):
    """
    MP3를 WAV로 변환 (pydub 사용)

    Args:
        mp3_path: MP3 파일 경로
        sample_rate: 목표 샘플 레이트

    Returns:
        WAV 파일 경로
    """
    try:
        from pydub import AudioSegment

        wav_path = mp3_path.with_suffix('.wav')

        print(f"  변환 중: MP3 → WAV ({sample_rate}Hz)")

        # MP3 로드
        audio = AudioSegment.from_mp3(str(mp3_path))

        # 샘플 레이트 변경 및 모노로 변환
        audio = audio.set_frame_rate(sample_rate)
        audio = audio.set_channels(1)  # 모노

        # WAV로 저장
        audio.export(str(wav_path), format='wav')

        print(f"  [Done] 변환 완료: {wav_path}")

        # MP3 삭제 (선택적)
        # mp3_path.unlink()

        return str(wav_path)

    except ImportError:
        print("  ⚠️  pydub가 설치되지 않았습니다. MP3 파일을 수동으로 변환해주세요.")
        return None
    except Exception as e:
        print(f"  [Error] 변환 에러: {e}")
        return None


def save_ground_truth(sentence_id: str, data: dict, audio_path: str, output_dir: Path):
    """
    Ground Truth 데이터 저장

    Args:
        sentence_id: 문장 ID
        data: 문장 데이터
        audio_path: 생성된 오디오 파일 경로
        output_dir: 출력 디렉토리
    """
    lang = data['lang']

    # Ground Truth 파일명
    gt_filename = f"{sentence_id}_groundtruth.json"
    gt_path = output_dir / gt_filename

    # Ground Truth 데이터
    ground_truth = {
        "sentence_id": sentence_id,
        "audio_file": audio_path,
        "language": lang,
        "transcription": data['text'],
        "duration_estimate": data.get('duration_estimate', 'N/A'),
        "created_at": datetime.now().isoformat(),
        "tts_engine": "gtts"
    }

    # 번역 추가
    if lang == "en" and "translation_ko" in data:
        ground_truth["translation_ko"] = data["translation_ko"]
    elif lang == "ko" and "translation_en" in data:
        ground_truth["translation_en"] = data["translation_en"]

    # JSON 저장
    with open(gt_path, 'w', encoding='utf-8') as f:
        json.dump(ground_truth, f, ensure_ascii=False, indent=2)

    print(f"  [Done] Ground Truth 저장: {gt_path}\n")


def generate_all_samples():
    """모든 샘플 생성"""
    # 출력 디렉토리
    voice_audio_dir = Path(__file__).parent.parent / "test_audio" / "voice_samples"
    ground_truth_dir = Path(__file__).parent.parent / "ground_truth"

    voice_audio_dir.mkdir(parents=True, exist_ok=True)
    ground_truth_dir.mkdir(parents=True, exist_ok=True)

    print("="*60)
    print("실제 음성 샘플 생성")
    print("="*60)
    print(f"출력 디렉토리: {voice_audio_dir}")
    print(f"Ground Truth: {ground_truth_dir}")
    print(f"총 {len(TEST_SENTENCES)}개 문장\n")

    generated_files = []

    for sentence_id, data in TEST_SENTENCES.items():
        print(f"\n[{sentence_id}]")

        # 1. gTTS로 MP3 생성
        mp3_path = generate_gtts_sample(sentence_id, data, voice_audio_dir)

        if mp3_path:
            # 2. MP3 → WAV 변환
            wav_path = convert_mp3_to_wav(Path(mp3_path), sample_rate=16000)

            if wav_path:
                # 3. Ground Truth 저장
                save_ground_truth(sentence_id, data, wav_path, ground_truth_dir)
                generated_files.append((sentence_id, wav_path))

    # 요약
    print("\n" + "="*60)
    print("생성 완료!")
    print("="*60)
    print(f"총 {len(generated_files)}개 파일 생성:\n")

    for sentence_id, wav_path in generated_files:
        print(f"  [Done] {sentence_id}: {Path(wav_path).name}")

    print(f"\n테스트 실행 예시:")
    if generated_files:
        first_file = generated_files[0][1]
        print(f"  python examples/test_transcription.py --service openai --file {first_file}")

    print("\n" + "="*60)


if __name__ == "__main__":
    generate_all_samples()
