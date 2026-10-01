from msclap import CLAP

class ClapModel:

    def __init__(self):
        self.model = CLAP(
            version="2023",
            use_cuda=False
        )

    def encode_audio(self, audio_path: str):
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
        return self.model.compute_similarity(
            audio_embeddings, 
            text_embeddings
        )
