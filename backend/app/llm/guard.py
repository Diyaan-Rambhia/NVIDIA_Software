"""Financial advice and prose format guardrails on the LLM output path."""

import json
import re
from functools import lru_cache
from pathlib import Path

from backend.app.config.loader import load_config_file
from backend.app.config.models import LexiconConfig
from backend.app.llm.exceptions import FinancialAdviceError, NonProseAnswerError

CONFIG_LEXICON_PATH = Path("config") / "lexicon.yaml"

TOOL_NAMES = [
    "f1_contagion",
    "f2_filings",
    "f3_portfolio",
    "tavily_search",
    "f2_lookup",
    "filings_check",
    "market_scan",
    "market_news",
    "trade_review",
]


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


def clean_prose_text(text: str) -> str:
    """Remove raw markdown asterisks and sanitize internal tool names from prose."""
    if not text:
        return ""

    # Replace **bold** with bold and remove stray **
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    cleaned = cleaned.replace("**", "")

    # Sanitize tool names into friendly domain descriptions
    for tool_name in TOOL_NAMES:
        friendly = tool_name.replace("_", " ").title()
        cleaned = re.sub(rf"\b{tool_name}\b", friendly, cleaned, flags=re.IGNORECASE)

    return cleaned


def assert_plain_prose(
    text: str,
    max_code_density: float = 0.20,
    max_json_density: float = 0.20,
) -> None:
    """Inspect output and raise NonProseAnswerError if the text is mostly code or JSON.

    Never shown to user; surfaces as a clear error: 'model returned a non-prose answer'.
    """
    if not text or not text.strip():
        raise NonProseAnswerError("model returned a non-prose answer")

    # 1. Code fence check
    if "```" in text:
        raise NonProseAnswerError("model returned a non-prose answer")

    stripped = text.strip()

    # 2. Check if the entire payload is raw JSON
    if (stripped.startswith("{") and stripped.endswith("}")) or (
        stripped.startswith("[") and stripped.endswith("]")
    ):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, (dict, list)):
                raise NonProseAnswerError("model returned a non-prose answer")
        except json.JSONDecodeError:
            pass

    # 3. Check for multi-line JSON blocks or high JSON syntax density
    json_chars = sum(1 for c in stripped if c in "{}\":[],")
    if len(stripped) > 20 and (json_chars / len(stripped)) > max_json_density:
        raise NonProseAnswerError("model returned a non-prose answer")

    # 4. Check for code syntax density
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if lines:
        code_starters = (
            "def ", "class ", "import ", "from ", "return ",
            "const ", "let ", "var ", "function ", "if (",
            "for (", "while (", "public ", "private ", "#include"
        )
        code_lines = sum(1 for line in lines if any(line.startswith(cs) for cs in code_starters))
        if (code_lines / len(lines)) > max_code_density:
            raise NonProseAnswerError("model returned a non-prose answer")

        # Code character punctuation density
        code_punct = sum(1 for c in stripped if c in "{}<>;=()")
        if len(stripped) > 40 and (code_punct / len(stripped)) > max_code_density:
            raise NonProseAnswerError("model returned a non-prose answer")
