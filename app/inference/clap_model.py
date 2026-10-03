from msclap import CLAP

class ClapModel:
    """기존 PoC·분류용 래퍼이며 서비스 검색의 공통 전처리 생성기와 구분한다."""

    def __init__(self):
        self.model = CLAP(
            version="2023",
            use_cuda=False
        )

    def encode_audio(self, audio_path: str):
        # MSCLAP은 파일 목록을 받으므로 단일 경로도 목록으로 감싼다.
        return self.model.get_audio_embeddings(
            [audio_path]
        )

    def encode_text(self, text: list[str]):
        return self.model.get_text_embeddings(
            text
        )

    def similarity(
        self, 
        audio_embeddings, 
        text_embeddings
    ):
        """MSCLAP의 배율 적용 유사도를 반환하며 원본 코사인 점수와 구분한다."""
        return self.model.compute_similarity(
            audio_embeddings, 
            text_embeddings
        )
