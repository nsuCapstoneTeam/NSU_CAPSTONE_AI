"""Docker Engine 없이 Compose의 실제 병합 결과와 필수 설정 거부를 검증한다."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which("docker"), "Docker Compose CLI is not installed")
class ComposeConfigurationTests(unittest.TestCase):
    def compose(self, *, development=False, missing=None):
        environment = dict(os.environ)
        # 개발자의 secret/.env/COMPOSE_FILE이 테스트 대상에 섞이지 않게 한다.
        for key in list(environment):
            if key.startswith(("DB_", "COMPOSE_")) or key in ("AI_IMAGE", "AI_PORT"):
                environment.pop(key)
        environment.update(DB_HOST="test-db", DB_PASSWORD="test-only-password")
        if missing:
            environment.pop(missing)
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / "empty.env"
            env_file.write_text("", encoding="utf-8")
            command = ["docker", "compose", "--env-file", str(env_file), "-f", str(ROOT / "compose.yaml")]
            if development:
                command += ["-f", str(ROOT / "compose.dev.yaml")]
            return subprocess.run(command + ["config", "--format", "json"], cwd=ROOT,
                                  env=environment, text=True, capture_output=True, timeout=30)

    def test_runtime_has_no_source_mount_or_reload(self):
        result = self.compose()
        self.assertEqual(result.returncode, 0, result.stderr)
        ai = json.loads(result.stdout)["services"]["ai"]
        self.assertNotIn("build", ai)
        self.assertIsNone(ai.get("command"))
        self.assertTrue(all(item["type"] == "volume" for item in ai["volumes"]))
        self.assertTrue(ai["volumes"][0]["read_only"])
        self.assertEqual(ai["environment"]["DB_HOST"], "test-db")

    def test_development_merges_writable_cache_and_readonly_sources(self):
        result = self.compose(development=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        ai = json.loads(result.stdout)["services"]["ai"]
        self.assertEqual(ai["image"], "nsu-capstone-ai:dev")
        self.assertEqual(ai["build"]["target"], "dev")
        self.assertIn("--reload", ai["command"])
        mounts = {item["target"]: item for item in ai["volumes"]}
        for folder in ("app", "scripts", "tests", "docs", "samples"):
            self.assertTrue(mounts[f"/workspace/{folder}"]["read_only"])
        self.assertFalse(mounts["/workspace/datasets"].get("read_only", False))
        self.assertFalse(mounts["/var/cache/huggingface"].get("read_only", False))
        self.assertEqual(len([item for item in ai["volumes"] if item["target"] == "/var/cache/huggingface"]), 1)

    def test_required_database_environment_fails_before_start(self):
        for development in (False, True):
            for variable in ("DB_HOST", "DB_PASSWORD"):
                with self.subTest(development=development, variable=variable):
                    result = self.compose(development=development, missing=variable)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(variable, result.stderr)


if __name__ == "__main__":
    unittest.main()
