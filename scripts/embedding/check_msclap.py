from importlib.metadata import version

from app.inference.clap_model import ClapModel


def main():
    print("msclap package:", version("msclap"))
    print("torch package:", version("torch"))
    print("model version: 2023")
    print("device: CPU")

    print("모델 로딩 시작...", flush=True)
    clap_model = ClapModel()

    print("모델 로딩 성공")
    print("wrapper:", type(clap_model.model).__name__)


if __name__ == "__main__":
    main()