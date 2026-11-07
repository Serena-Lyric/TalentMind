import json
from pathlib import Path
import subprocess
import sys


def test_manifest_path_traversal_is_rejected_before_output_or_model_access(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"records": [{"sample": "../escape", "pairs": []}]}))
    output = tmp_path / "out"
    script = Path(__file__).resolve().parents[2] / "scripts/run_m2_fixed_work_pairs.py"
    result = subprocess.run([sys.executable, str(script), "--manifest", str(manifest), "--model", "absent.json",
                             "--output", str(output)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "unique safe path component" in result.stderr
    assert not output.exists()


def test_public_repository_output_is_rejected_before_any_writes(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"records": []}))
    backend = Path(__file__).resolve().parents[2]
    output = backend / "forbidden-fixed-pair-output"
    result = subprocess.run([sys.executable, str(backend / "scripts/run_m2_fixed_work_pairs.py"),
        "--manifest", str(manifest), "--model", "absent.json", "--output", str(output)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "repository outputs must be under data/local" in result.stderr
    assert not output.exists()
