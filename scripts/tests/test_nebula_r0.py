"""Pure-memory research checks; no services or production writers."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import os
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nebula_r0 import ari, digest, partition, projection, research, topology


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.raw = {
            "nodes": [{"id": j, "type": "job", "name": j} for j in ("j1", "j2", "j3", "j4")] + [{"id": s, "type": "skill", "name": s} for s in ("s1", "s2", "s3")],
            "edges": [{"source": j, "target": s, "type": "REQUIRES"} for j, s in [("j1", "s1"), ("j2", "s1"), ("j2", "s2"), ("j3", "s2"), ("j4", "s3")]],
        }

    def test_projection_uses_actual_intersection_union_and_retains_isolates(self):
        skills = topology(self.raw)[4]
        result = projection(skills)
        self.assertAlmostEqual(result["j1"]["j2"]["weight"], .5)
        self.assertFalse(result.has_edge("j1", "j3"))
        self.assertIn("j4", result)
        self.assertEqual(result.degree["j4"], 0)

    def test_same_input_and_shuffled_input_have_identical_protocol(self):
        before = deepcopy(self.raw)
        _, first = research(self.raw)
        _, second = research({"nodes": self.raw["nodes"][::-1], "edges": self.raw["edges"][::-1]})
        self.assertEqual(digest(first), digest(second))
        self.assertEqual(self.raw, before)
        self.assertEqual(len(first["nodes"]), 7)

    def test_invalid_identity_or_edge_is_rejected(self):
        for broken in (dict(self.raw, nodes=self.raw["nodes"] + [self.raw["nodes"][0]]), dict(self.raw, edges=self.raw["edges"] + [{"source": "missing", "target": "s1", "type": "REQUIRES"}])):
            with self.assertRaises(ValueError):
                topology(broken)

    def test_ari_partition_label_independence(self):
        self.assertEqual(ari([{"a", "b"}, {"c"}], [{"c"}, {"b", "a"}]), 1)
        self.assertLess(ari([{"a", "b"}, {"c", "d"}], [{"a", "c"}, {"b", "d"}]), 0)

    def test_full_snapshot_stable_across_process_hash_seeds(self):
        root = Path(__file__).resolve().parents[2]
        code = "import sys,json;sys.path.insert(0,'scripts');from pathlib import Path;from nebula_r0 import research,digest;print(digest(research(json.loads(Path('exchange/m3/graph.json').read_text(encoding='utf8')))[1]))"
        outputs = []
        for seed in ("1", "2"):
            outputs.append(subprocess.run([sys.executable, "-c", code], cwd=root, env={**os.environ, "PYTHONHASHSEED": seed}, capture_output=True, text=True, check=True).stdout.strip())
        self.assertEqual(*outputs)


if __name__ == "__main__":
    unittest.main()
