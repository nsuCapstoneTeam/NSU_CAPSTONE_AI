import torch

class AudioClassifier:
    def __init__(self, clap_model):
        self.clap_model = clap_model

    def classify(self, audio_embeddings, labels: list[str],top_k: int = 3):

            # 라벨 텍스트를 임베딩으로 반환
            text_embeddings = self.clap_model.encode_text(
                labels
            )

            # 오디오와 텍스트 임베딩 간 유사도 계산
            similarities = self.clap_model.similarity(
                audio_embeddings, 
                text_embeddings
            )

            probabilities = torch.softmax(similarities, dim=1)

            similarities_scores = similarities[0]
            probabilities_scores = probabilities[0]

            # PyTorch Tensor -> Python list
            if isinstance(similarities_scores, torch.Tensor):
                similarities_scores = similarities_scores.detach().cpu().tolist()

            if isinstance(probabilities_scores, torch.Tensor):
                            probabilities_scores = probabilities_scores.detach().cpu().tolist()

            # label + score 묶기
            results = []

            for label, similarity, probability in zip(labels, similarities_scores, probabilities_scores):
                results.append({
                    "label": label,
                    "similarity": float(similarity),
                    "probability": float(probability)
                })

            # score 높은 순서대로 정렬
            results.sort(key=lambda x: x["similarity"], reverse=True)

            # TOP K 결과만 반환
            return results[:top_k]
