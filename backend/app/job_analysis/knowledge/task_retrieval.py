"""Optional local cross-encoder for priority only; no semantic admission by score."""
import importlib.metadata
from pathlib import Path

from .local_semantics import _local, file_digest
from .models import Strict, Text, Sha256
from ..foundation.inputs import digest, parse_json


class RetrieverManifest(Strict):
    repository: Text
    revision: Text
    license: Text
    files: dict[str, Sha256]


class LocalTaskRetriever:
    def __init__(self, path):
        self.path = Path(path).resolve(strict=True)
        self.manifest = RetrieverManifest.model_validate(parse_json(self.path.read_text(encoding="utf-8-sig")))
        self._verify()
        config = parse_json((self.path.parent / "config.json").read_text(encoding="utf-8"))
        if config.get("id2label") != {"0": "entailment", "1": "neutral", "2": "contradiction"}:
            raise ValueError("unsupported retrieval logit labels")
        # Imports never occur on ordinary CLI, historical reads, or CI without
        # an explicitly supplied retriever. These APIs read local files only.
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError:
            raise ValueError("local task retrieval dependencies unavailable") from None
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        self.session = ort.InferenceSession(str(self.path.parent / "model.onnx"), options,
                                           providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(str(self.path.parent / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=512)
        self.tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
        self.binding = dict(id=self.manifest.repository, revision=self.manifest.revision,
            sha256=digest(self.manifest.model_dump()), files=self.manifest.files,
            runtime={p: importlib.metadata.version(p) for p in ["onnxruntime", "tokenizers", "numpy"]},
            max_tokens=512, score_use="priority_only_not_support_or_confidence")

    def _verify(self):
        if set(self.manifest.files) != {"config.json", "model.onnx", "tokenizer.json"}:
            raise ValueError("retriever needs exact local file set")
        for relative, sha in self.manifest.files.items():
            if file_digest(_local(self.path.parent, relative)) != sha:
                raise ValueError("retriever file digest mismatch")

    def rank(self, pairs):
        import numpy as np
        self._verify()
        result = []
        for offset in range(0, len(pairs), 16):
            encodings = self.tokenizer.encode_batch(pairs[offset:offset+16])
            logits = self.session.run(None, dict(
                input_ids=np.array([e.ids for e in encodings], dtype=np.int64),
                attention_mask=np.array([e.attention_mask for e in encodings], dtype=np.int64)))[0]
            scores = np.exp(logits - logits.max(axis=1, keepdims=True))
            scores /= scores.sum(axis=1, keepdims=True)
            result.extend((float(score[0]), bool(e.overflowing)) for score, e in zip(scores, encodings))
        return result
