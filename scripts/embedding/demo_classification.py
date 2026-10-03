"""샘플·모델이 필요한 수동 PoC이며 데이터 없는 tests/ 자동 테스트와 구분한다."""

from app.inference.clap_model import ClapModel
from app.classification.classifier import AudioClassifier
from app.classification.labels import (
    GENRE_LABELS, 
    MOOD_LABELS,
    SOUND_LABELS
)

clap_model = ClapModel()

classifier = AudioClassifier(clap_model)

audio_embeddings = clap_model.encode_audio(
    "samples/sample.wav"
)

results = classifier.classify(
    audio_embeddings,
    labels=GENRE_LABELS,
    top_k=3
)

print("=== Genre TOP 3 ===")

for rank, result in enumerate(results, start=1):
    print(
        f"{rank}. "
        f"{result['label']} | "
        f"유사도: {result['similarity']:.4f} | "
        f"상대점수: {result['probability'] * 100:.2f}%"
    )
