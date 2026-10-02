from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parents[1]
    audio_path = project_root / "samples" / "sample.wav"

    # Check the input before importing or loading the model.
    if not audio_path.is_file():
        raise FileNotFoundError(f"음원 파일이 없습니다: {audio_path}")

    import torch
    from app.inference.clap_model import ClapModel

    print("audio:", audio_path)
    print("모델 로딩 시작...", flush=True)
    clap_model = ClapModel()

    print("오디오 임베딩 생성 시작...", flush=True)
    with torch.inference_mode():
        embeddings = clap_model.encode_audio(str(audio_path))

    if embeddings.ndim != 2 or embeddings.shape[0] != 1 or embeddings.shape[1] == 0:
        raise ValueError(f"예상하지 못한 임베딩 shape: {tuple(embeddings.shape)}")
    if not torch.isfinite(embeddings).all().item():
        raise ValueError("임베딩에 NaN 또는 Inf가 있습니다")

    print("shape:", tuple(embeddings.shape))
    print("dimension:", embeddings.shape[1])
    print("dtype:", embeddings.dtype)
    print("device:", embeddings.device)
    print("norm:", embeddings.norm(dim=1).detach().cpu().tolist())
    print("오디오 임베딩 검증 성공")


if __name__ == "__main__":
    main()
