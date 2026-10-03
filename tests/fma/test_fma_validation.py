"""표본·입력 처리는 가짜 메타데이터와 모델로 검사해 음원·가중치 다운로드를 피한다."""
import csv
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path

from scripts.fma.validate_fma import GENRES, bounded_text_embeddings, check_embedding, select_tracks


class FmaSelectionTests(unittest.TestCase):
    def test_official_headers_split_paths_licenses_and_repeatable_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            metadata = root / "tracks.csv"
            with metadata.open("w", newline="", encoding="utf-8") as target:
                writer = csv.writer(target)
                writer.writerow(["", "set", "set", "track", "track", "track"])
                writer.writerow(["", "subset", "split", "genre_top", "title", "license"])
                writer.writerow(["track_id", "", "", "", "", ""])
                for number, genre in enumerate(GENRES):
                    for offset in range(3):
                        track_id = number * 1000 + offset + 1
                        name = f"{track_id:06d}"
                        path = root / name[:3] / f"{name}.mp3"
                        path.parent.mkdir(exist_ok=True)
                        path.touch()
                        writer.writerow([track_id, "small", "test" if offset < 2 else "training",
                                         genre, "Title, quoted", "CC BY"])
            selected = select_tracks(metadata, root, 2, 42, "test")
            self.assertEqual(len(selected), 16)
            self.assertEqual(selected, select_tracks(metadata, root, 2, 42, "test"))
            self.assertTrue(all(track["license"] == "CC BY" for track in selected))
            self.assertTrue(all(track["track_id"] % 1000 in (1, 2) for track in selected))
            Path(selected[0]["audio_path"]).unlink()
            with self.assertRaisesRegex(ValueError, "local files"):
                select_tracks(metadata, root, 2, 42, "test")


class FmaEmbeddingTests(unittest.TestCase):
    def test_mixed_long_short_inputs_are_bounded_and_audited(self):
        import torch

        class Tokenizer:
            def encode(self, text, **kwargs):
                return [ord(character) for character in text]

            def encode_plus(self, text, max_length, truncation=False, **kwargs):
                tokens = self.encode(text)
                if truncation:
                    tokens = tokens[:max_length]
                padding = max(0, max_length - len(tokens))
                return {"input_ids": torch.tensor([tokens + [0] * padding]),
                        "attention_mask": torch.tensor([[1] * len(tokens) + [0] * padding])}

            def decode(self, tokens, **kwargs):
                return "".join(chr(token) for token in tokens)

        class Model:
            args = SimpleNamespace(text_len=77)

            def __init__(self):
                self.tokenizer = Tokenizer()

            def get_text_embeddings(self, texts):
                # 가중치 없이도 MSCLAP의 길이 제한 없는 패딩 배치 실패를 재현한다.
                encoded = [self.tokenizer.encode_plus(text=text, max_length=77)["input_ids"]
                           .reshape(-1) for text in texts]
                return torch.stack(encoded)

        model = Model()
        tokenizer = model.tokenizer
        with self.assertRaises(RuntimeError):
            model.get_text_embeddings(["a" * 100, "ok"])
        result, audit = bounded_text_embeddings(model, ["a" * 100, "ok"])
        self.assertEqual(tuple(result.shape), (2, 77))
        self.assertEqual([item["truncated"] for item in audit["prompts"]], [True, False])
        self.assertEqual(audit["prompts"][0]["original_tokens"], 100)
        self.assertEqual(audit["prompts"][0]["effective_text"], "a" * 77)
        self.assertEqual(audit["prompts"][1]["effective_text"], "ok")
        self.assertIs(model.tokenizer, tokenizer)

    def test_tokenizer_is_restored_after_embedding_failure(self):
        tokenizer = object()
        model = SimpleNamespace(tokenizer=tokenizer, args=SimpleNamespace(text_len=77),
                                get_text_embeddings=Mock(side_effect=RuntimeError("model failure")))
        with self.assertRaisesRegex(RuntimeError, "model failure"):
            bounded_text_embeddings(model, ["text"])
        self.assertIs(model.tokenizer, tokenizer)

    def test_invalid_embeddings_are_rejected(self):
        import torch

        for tensor in (torch.zeros(1, 3), torch.tensor([[float("nan"), 1.0]]),
                       torch.tensor([[float("inf"), 1.0]]), torch.ones(3)):
            with self.subTest(tensor=tensor):
                with self.assertRaises(ValueError):
                    check_embedding(tensor, 1)
        with self.assertRaisesRegex(ValueError, "dimensions differ"):
            check_embedding(torch.ones(1, 3), 1, dimension=4)
        check_embedding(torch.ones(1, 3), 1, dimension=3)


if __name__ == "__main__":
    unittest.main()
