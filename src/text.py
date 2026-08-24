import re
from collections.abc import Mapping

def replace_words(text: str, replacements: Mapping[str, str]) -> str:
    normalized = {key.casefold(): value for key, value in replacements.items()}

    pattern = re.compile(
        r"\b(" + "|".join(map(re.escape, replacements)) + r")\b",
        flags=re.IGNORECASE,
    )

    return pattern.sub(
        lambda match: normalized[match.group(0).casefold()],
        text
    )
