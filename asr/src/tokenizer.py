"""tokenizer.py — Whisper token IDs ↔ English text via HuggingFace `tokenizers`.

Whisper-tiny.en special tokens (from tokenizer.json):
  <|endoftext|>           = 50256
  <|startoftranscript|>   = 50257
  <|translate|>           = 50358
  <|transcribe|>          = 50359
  <|notimestamps|>        = 50362
"""
from __future__ import annotations

from pathlib import Path


class WhisperTokenizer:
    def __init__(self, tokenizer_path):
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))

        # Cache common special token IDs (None if not present in this vocab)
        self.EOT_ID = self._safe_token_id("<|endoftext|>")
        self.SOT_ID = self._safe_token_id("<|startoftranscript|>")
        self.NOTIMESTAMPS_ID = self._safe_token_id("<|notimestamps|>")

    def _safe_token_id(self, token):
        try:
            return self.tokenizer.token_to_id(token)
        except Exception:
            return None

    def decode(self, token_ids):
        """Decode token ID sequence to English text.

        Accepts: np.ndarray (1, N) | list[int] | list[list[int]].
        Drops special tokens, padding (-1 / 0), and everything after first EOT.
        """
        if hasattr(token_ids, "tolist"):
            token_ids = token_ids.tolist()
        if isinstance(token_ids, list) and len(token_ids) > 0 and isinstance(token_ids[0], list):
            token_ids = token_ids[0]  # flatten batch dim

        cleaned = []
        for t in token_ids:
            t = int(t)
            # Pad / invalid
            if t < 0:
                continue
            # End of transcript
            if self.EOT_ID is not None and t == self.EOT_ID:
                break
            cleaned.append(t)

        text = self.tokenizer.decode(cleaned, skip_special_tokens=True)
        return text.strip()


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Quick tokenizer round-trip test.")
    ap.add_argument("tokenizer_json")
    ap.add_argument("--text", default="Hello robot, come here.")
    args = ap.parse_args()

    tok = WhisperTokenizer(args.tokenizer_json)
    enc = tok.tokenizer.encode(args.text)
    print(f"encoded ({len(enc.ids)} tokens): {enc.ids}")
    print(f"decoded: {tok.decode(enc.ids)}")
    print(f"EOT={tok.EOT_ID} SOT={tok.SOT_ID} NOTIMESTAMPS={tok.NOTIMESTAMPS_ID}")
