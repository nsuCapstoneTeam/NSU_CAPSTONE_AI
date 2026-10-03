import torch

class AudioClassifier:
    """주어진 라벨 사이의 상대 순위를 비교하는 단일 음악 PoC 분류기."""
    def __init__(self, clap_model):
        self.clap_model = clap_model

    def classify(self, audio_embeddings, labels: list[str],top_k: int = 3):
            """첫 오디오의 라벨별 유사도와 상대점수를 반환한다.

            probability는 입력 라벨 집합 안에서의 softmax 값이며 실제 장르 확률이나
            행사 적합 확률로 해석하지 않는다. 라벨 집합이 바뀌면 상대점수도 바뀐다.
            """

            text_embeddings = self.clap_model.encode_text(
                labels
            )

            similarities = self.clap_model.similarity(
                audio_embeddings, 
                text_embeddings
            )

            probabilities = torch.softmax(similarities, dim=1)

            similarities_scores = similarities[0]
            probabilities_scores = probabilities[0]

            # 추론 텐서가 외부 결과에 남지 않도록 그래프를 분리하고 CPU 기본 자료형으로 변환한다.
            if isinstance(similarities_scores, torch.Tensor):
                similarities_scores = similarities_scores.detach().cpu().tolist()

            if isinstance(probabilities_scores, torch.Tensor):
                            probabilities_scores = probabilities_scores.detach().cpu().tolist()

            results = []

            for label, similarity, probability in zip(labels, similarities_scores, probabilities_scores):
                results.append({
                    "label": label,
                    "similarity": float(similarity),
                    "probability": float(probability)
                })

            results.sort(key=lambda x: x["similarity"], reverse=True)

            return results[:top_k]
