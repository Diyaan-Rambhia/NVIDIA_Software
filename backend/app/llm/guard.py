"""Financial advice guardrail on the LLM output path."""

import re
from functools import lru_cache
from pathlib import Path

from backend.app.config.loader import load_config_file
from backend.app.config.models import LexiconConfig
from backend.app.llm.exceptions import FinancialAdviceError

CONFIG_LEXICON_PATH = Path("config") / "lexicon.yaml"


@lru_cache(maxsize=1)
def get_prohibited_advice_patterns(config_path: Path | None = None) -> list[re.Pattern[str]]:
    """Compile prohibited advice regex patterns dynamically from config/lexicon.yaml."""
    path = config_path or CONFIG_LEXICON_PATH
    lexicon = load_config_file(path, LexiconConfig)
    patterns: list[re.Pattern[str]] = []
    for phrase in lexicon.prohibited_advice_phrases:
        escaped = r"\s+".join(re.escape(word) for word in phrase.split())
        patterns.append(re.compile(rf"\b{escaped}\b", re.IGNORECASE))
    return patterns


def assert_no_financial_advice(text: str, config_path: Path | None = None) -> None:
    """Inspect generated text and raise FinancialAdviceError if prohibited advice is detected.

    FinInsight is educational and analytical only. The model has no authority
    to emit buy, sell, or hold recommendations (PROJECT.md §2.1 and §8.2).
    """
    if not text:
        return

    patterns = get_prohibited_advice_patterns(config_path)
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            prohibited_phrase = match.group(0)
            raise FinancialAdviceError(
                f"Prohibited financial advice detected in model output: '{prohibited_phrase}'. "
                "FinInsight does not provide investment recommendations."
            )
