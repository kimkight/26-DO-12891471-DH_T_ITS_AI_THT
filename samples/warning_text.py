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
