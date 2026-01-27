#!/usr/bin/env python3
"""Ground Truth JSON 파일 생성"""

import json
from pathlib import Path
from datetime import datetime

voice_samples_dir = Path(__file__).parent.parent / 'test_audio' / 'voice_samples'
ground_truth_dir = Path(__file__).parent.parent / 'ground_truth'
ground_truth_dir.mkdir(exist_ok=True)

test_sentences = {
    'en_short': {
        'text': 'Hello, how are you today?',
        'lang': 'en',
        'translation_ko': '안녕하세요, 오늘 어떻게 지내세요?'
    },
    'en_medium': {
        'text': "The weather is beautiful today. I think it's a perfect day for a walk in the park.",
        'lang': 'en',
        'translation_ko': '오늘 날씨가 아름답네요. 공원에서 산책하기 완벽한 날인 것 같아요.'
    },
    'en_long': {
        'text': 'Artificial intelligence is transforming the way we live and work. From voice assistants to self-driving cars, AI technologies are becoming an integral part of our daily lives.',
        'lang': 'en',
        'translation_ko': '인공지능은 우리가 살고 일하는 방식을 변화시키고 있습니다. 음성 비서부터 자율주행차까지, AI 기술은 우리 일상생활의 필수적인 부분이 되어가고 있습니다.'
    },
    'en_technical': {
        'text': 'Machine learning models require large amounts of training data to achieve high accuracy. The quality of data is just as important as the quantity.',
        'lang': 'en',
        'translation_ko': '머신러닝 모델은 높은 정확도를 달성하기 위해 많은 양의 훈련 데이터가 필요합니다. 데이터의 품질은 양만큼이나 중요합니다.'
    },
    'ko_short': {
        'text': '안녕하세요, 만나서 반갑습니다.',
        'lang': 'ko',
        'translation_en': 'Hello, nice to meet you.'
    },
    'ko_medium': {
        'text': '저는 오늘 새로운 프로젝트를 시작했습니다. 매우 흥미롭고 도전적인 작업이에요.',
        'lang': 'ko',
        'translation_en': "I started a new project today. It's a very interesting and challenging task."
    },
    'ko_long': {
        'text': '인공지능 기술의 발전은 우리 사회에 많은 변화를 가져오고 있습니다. 특히 번역 기술의 발전으로 언어의 장벽이 점점 낮아지고 있습니다.',
        'lang': 'ko',
        'translation_en': 'The advancement of artificial intelligence technology is bringing many changes to our society. Especially, the development of translation technology is gradually lowering language barriers.'
    }
}

print("Ground Truth JSON 파일 생성 중...\n")

for sentence_id, data in test_sentences.items():
    wav_file = voice_samples_dir / f'{sentence_id}_gtts.wav'

    gt = {
        'sentence_id': sentence_id,
        'audio_file': str(wav_file),
        'language': data['lang'],
        'transcription': data['text'],
        'created_at': datetime.now().isoformat(),
        'tts_engine': 'gtts'
    }

    if data['lang'] == 'en':
        gt['translation_ko'] = data['translation_ko']
    else:
        gt['translation_en'] = data['translation_en']

    gt_file = ground_truth_dir / f'{sentence_id}_groundtruth.json'
    with open(gt_file, 'w', encoding='utf-8') as f:
        json.dump(gt, f, ensure_ascii=False, indent=2)

    print(f'[Done] {gt_file.name}')

print(f"\n총 {len(test_sentences)}개 Ground Truth 파일 생성 완료!")
print(f"위치: {ground_truth_dir}")
