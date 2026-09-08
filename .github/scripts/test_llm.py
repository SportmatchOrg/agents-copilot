import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SCRIPT = REPO_ROOT / "github" / "scripts" / "llm.sh"

MOCK_CURL = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
payload = json.loads(args[args.index("-d") + 1])
model = payload["model"]
log_path = Path(os.environ["MOCK_REQUEST_LOG"])
previous = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
attempt = previous.count(model)
with log_path.open("a", encoding="utf-8") as log:
    log.write(model + "\n")

responses = json.loads(os.environ["MOCK_RESPONSES"])[model]
status, body = responses[min(attempt, len(responses) - 1)]
print(json.dumps(body))
print(status)
'''


class LlmScriptTests(unittest.TestCase):
    def run_llm(self, responses, *, model, fallbacks=None):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            prompt = temp_path / "prompt.txt"
            prompt.write_text("Estado del sprint", encoding="utf-8")

            fake_bin = temp_path / "bin"
            fake_bin.mkdir()
            fake_curl = fake_bin / "curl"
            fake_curl.write_text(MOCK_CURL, encoding="utf-8")
            fake_curl.chmod(0o755)
            fake_sleep = fake_bin / "sleep"
            fake_sleep.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            fake_sleep.chmod(0o755)
            request_log = temp_path / "requests.log"

            env = os.environ.copy()
            env.update(
                {
                    "LLM_API_KEY": "test-key",
                    "LLM_BASE_URL": "https://example.test/chat/completions",
                    "LLM_MODEL": model,
                    "MOCK_REQUEST_LOG": str(request_log),
                    "MOCK_RESPONSES": json.dumps(responses),
                    "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                }
            )
            if fallbacks is not None:
                env["LLM_FALLBACK_MODELS"] = fallbacks
            else:
                env.pop("LLM_FALLBACK_MODELS", None)

            result = subprocess.run(
                ["bash", str(LLM_SCRIPT), str(prompt)],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            requests = request_log.read_text(encoding="utf-8").splitlines()

        return result, requests

    def test_removed_free_model_falls_back_to_openrouter_free(self):
        result, requests = self.run_llm(
            {
                "minimax/minimax-m3:free": [
                    [404, {"error": {"message": "free model retired"}}]
                ],
                "openrouter/free": [
                    [200, {"choices": [{"message": {"content": "Estado amarillo"}}]}]
                ],
            },
            model="minimax/minimax-m3:free",
        )

        self.assertEqual(result.stdout.strip(), "Estado amarillo")
        self.assertEqual(
            requests, ["minimax/minimax-m3:free", "openrouter/free"]
        )
        self.assertIn("probando fallback", result.stderr)

    def test_transient_error_retries_before_fallback(self):
        result, requests = self.run_llm(
            {
                "primary-free": [
                    [503, {"error": {"message": "overloaded"}}],
                    [200, {"choices": [{"message": {"content": "Estado verde"}}]}],
                ],
                "openrouter/free": [
                    [200, {"choices": [{"message": {"content": "fallback"}}]}]
                ],
            },
            model="primary-free",
            fallbacks="openrouter/free",
        )

        self.assertEqual(result.stdout.strip(), "Estado verde")
        self.assertEqual(requests, ["primary-free", "primary-free"])

    def test_reports_unavailable_only_after_all_models_fail(self):
        responses = {
            model: [[404, {"error": {"message": f"{model} unavailable"}}]]
            for model in ("retired:free", "another:free", "openrouter/free")
        }
        result, requests = self.run_llm(
            responses,
            model="retired:free",
            fallbacks="another:free, openrouter/free",
        )

        self.assertEqual(
            requests, ["retired:free", "another:free", "openrouter/free"]
        )
        self.assertIn("LLM_UNAVAILABLE: todos los modelos fallaron", result.stdout)
        self.assertIn("último=openrouter/free HTTP 404", result.stdout)


if __name__ == "__main__":
    unittest.main()
