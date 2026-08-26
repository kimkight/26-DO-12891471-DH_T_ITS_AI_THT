"""The 27 CFR 16.21 statement, for sample tooling that must not import the app.

The sample set is input to the application, so it cannot take its ground truth
from the application's own constant: a typo in app/warning.py would then be
copied into the artwork and the accuracy run would score it as correct. This
copy is checked against the requirements document by
backend/tests/test_samples.py, which is the same document app/warning.py is
checked against.

Quoted verbatim from docs/03_REQUIREMENTS.md section 1.
"""

WARNING_STATEMENT = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability to "
    "drive a car or operate machinery, and may cause health problems."
)


# The three words the label photographed in the first real-artwork test split
# across line breaks with a printer's hyphen. Written as head and tail so the
# column below is derived from the statement above rather than retyped: a
# fixture that repeats the regulation is a second source of truth for it.
HYPHENATED_SPLITS = {
    "According": ("Ac", "cording"),
    "General,": ("Gen", "eral,"),
    "Consumption": ("Consump", "tion"),
}


def hyphenated_column(statement: str = WARNING_STATEMENT, width: int = 30) -> str:
    """Set the statement in a narrow column, hyphenating as a real label does.

    A bottle carries the warning in a column a few words wide, and the setter
    hyphenates long words to fill it. That is presentation, not wording, so a
    label that does it has to still match 27 CFR 16.21 (assumption A-15). This
    renders that case: the returned string carries explicit line breaks, which
    samples/labelmaker.py honours rather than reflowing.
    """
    lines: list[str] = []
    current = ""
    for word in statement.split():
        split = HYPHENATED_SPLITS.get(word)
        if split is not None:
            head, tail = split
            lines.append(f"{current} {head}-".strip())
            current = tail
            continue
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines)
