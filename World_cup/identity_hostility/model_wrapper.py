"""
model_wrapper.py
Wraps Detoxify multilingual for batched identity-hostility scoring.

Supported languages (Detoxify multilingual):
    en, fr, es, it, pt, tr, ru
Comments in other languages get score=None (model_unsupported).
"""

from __future__ import annotations

from typing import Iterator, Sequence

from identity_common import log


class IdentityScorer:
    """Batched Detoxify multilingual scorer.

    Parameters
    ----------
    model_id : str
        HuggingFace model id, from flag_config.json.
    identity_head : str
        Primary output head to use (e.g. 'identity_attack').
    fallback_head : str
        Head used if identity_head not present in model outputs.
    batch_size : int
    max_chars : int
        Text is truncated to this many characters before inference to avoid
        tokeniser overflow. Detoxify internally also truncates to 512 tokens,
        but string-level truncation keeps memory predictable.
    """

    def __init__(
        self,
        model_id: str = "multilingual",
        identity_head: str = "identity_attack",
        fallback_head: str = "toxicity",
        batch_size: int = 64,
        max_chars: int = 512,
    ) -> None:
        self.model_id = model_id
        self.identity_head = identity_head
        self.fallback_head = fallback_head
        self.batch_size = batch_size
        self.max_chars = max_chars
        self._model = None
        self._active_head: str | None = None

    def _load(self) -> None:
        if self._model is not None:
            return
        log(f"[model] Loading {self.model_id} ...")
        try:
            from detoxify import Detoxify
        except ImportError:
            raise RuntimeError(
                "detoxify is not installed. Run: pip install detoxify"
            )
        self._model = Detoxify(self.model_id)
        # Detect which output head is available
        test_result = self._model.predict("test")
        if self.identity_head in test_result:
            self._active_head = self.identity_head
        elif self.fallback_head in test_result:
            self._active_head = self.fallback_head
            log(
                f"[model] WARNING: '{self.identity_head}' not found in model outputs; "
                f"using fallback '{self.fallback_head}'. Scores may be less precise."
            )
        else:
            available = list(test_result.keys())
            raise RuntimeError(
                f"Neither '{self.identity_head}' nor '{self.fallback_head}' "
                f"found in model outputs. Available: {available}"
            )
        log(f"[model] Loaded. Active head: {self._active_head}")

    def score_batch(self, texts: list[str]) -> list[float]:
        """Score a batch of texts. Returns a list of floats in [0, 1]."""
        self._load()
        truncated = [t[: self.max_chars] if t else "" for t in texts]
        result = self._model.predict(truncated)
        scores = result[self._active_head]
        if hasattr(scores, "tolist"):
            return scores.tolist()
        if not isinstance(scores, list):
            return list(scores)
        return scores

    def score_batched_iter(
        self, texts: Sequence[str]
    ) -> Iterator[float]:
        """Yield one float score per text, processing in batches."""
        batch: list[str] = []
        for text in texts:
            batch.append(text or "")
            if len(batch) >= self.batch_size:
                yield from self.score_batch(batch)
                batch = []
        if batch:
            yield from self.score_batch(batch)
