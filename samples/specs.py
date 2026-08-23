"""The twelve synthetic labels and the application data submitted against them.

The set is built from the cases samples/README.md lists, which are themselves
drawn from the interviews, plus the beverage classes 27 CFR names and the image
defects Jenny Park describes ("photographed at weird angles, or the lighting is
bad"). Nothing here is invented beyond the brand names, which have to be
something: they are fictional and deliberately unlike any real trade dress.

Each spec carries both sides of a test case. ``LabelSpec`` fields describe what
is printed on the artwork; ``application`` is what the applicant declared, in
the A-14 column names, and is what the label is compared against.
"""

from __future__ import annotations

from samples.labelmaker import LabelSpec
from samples.warning_text import WARNING_STATEMENT

TITLE_CASE_WARNING = WARNING_STATEMENT.replace("GOVERNMENT WARNING:", "Government Warning:")
ALTERED_WARNING = WARNING_STATEMENT.replace(
    "women should not drink alcoholic beverages during pregnancy",
    "women should avoid alcoholic beverages during pregnancy",
)

SAMPLE_LABEL = LabelSpec(
    filename="01-spirits-clean.png",
    brand_name="STONE'S THROW",
    class_type="Kentucky Straight Bourbon Whiskey",
    alcohol_content="45% Alc./Vol. (90 Proof)",
    net_contents="750 mL",
    warning=WARNING_STATEMENT,
    beverage_type="distilled spirits",
    notes="Clean label; every field agrees with the application.",
    application={
        "brand_name": "Stone's Throw",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "45",
        "net_contents": "750 mL",
        "beverage_type": "distilled spirits",
    },
)

SPECS: list[LabelSpec] = [
    SAMPLE_LABEL,
    LabelSpec(
        filename="02-spirits-case-difference.png",
        brand_name="STONE'S THROW",
        class_type="Kentucky Straight Bourbon Whiskey",
        alcohol_content="45% Alc./Vol. (90 Proof)",
        net_contents="750 mL",
        warning=WARNING_STATEMENT,
        beverage_type="distilled spirits",
        notes="Dave Morrison's case: upper case on the label, title case on the form.",
        application={
            "brand_name": "Stone's Throw",
            "class_type": "Kentucky Straight Bourbon Whiskey",
            "alcohol_content": "45%",
            "net_contents": "750ml",
            "beverage_type": "distilled spirits",
        },
    ),
    LabelSpec(
        filename="03-spirits-title-case-warning.png",
        brand_name="COPPER KETTLE",
        class_type="Straight Rye Whiskey",
        alcohol_content="50% Alc./Vol. (100 Proof)",
        net_contents="750 mL",
        warning=TITLE_CASE_WARNING,
        beverage_type="distilled spirits",
        notes="Defect: warning prefix in title case. Jenny Park's rejected case.",
        application={
            "brand_name": "Copper Kettle",
            "class_type": "Straight Rye Whiskey",
            "alcohol_content": "50",
            "net_contents": "750 mL",
            "beverage_type": "distilled spirits",
        },
    ),
    LabelSpec(
        filename="04-spirits-altered-warning.png",
        brand_name="SALT MARSH",
        class_type="Blended Whiskey",
        alcohol_content="40% Alc./Vol. (80 Proof)",
        net_contents="750 mL",
        warning=ALTERED_WARNING,
        beverage_type="distilled spirits",
        notes="Defect: one word of the warning altered, should not drink to should avoid.",
        application={
            "brand_name": "Salt Marsh",
            "class_type": "Blended Whiskey",
            "alcohol_content": "40",
            "net_contents": "750 mL",
            "beverage_type": "distilled spirits",
        },
    ),
    LabelSpec(
        filename="05-spirits-no-warning.png",
        brand_name="LANTERN HILL",
        class_type="London Dry Gin",
        alcohol_content="47% Alc./Vol. (94 Proof)",
        net_contents="750 mL",
        warning=None,
        beverage_type="distilled spirits",
        notes="Defect: no government warning statement at all.",
        application={
            "brand_name": "Lantern Hill",
            "class_type": "London Dry Gin",
            "alcohol_content": "47",
            "net_contents": "750 mL",
            "beverage_type": "distilled spirits",
        },
    ),
    LabelSpec(
        filename="06-spirits-wrong-abv.png",
        brand_name="TWO RIVERS",
        class_type="Silver Rum",
        alcohol_content="40% Alc./Vol. (80 Proof)",
        net_contents="750 mL",
        warning=WARNING_STATEMENT,
        beverage_type="distilled spirits",
        notes="Defect: the application declares 40.5 percent against 40 on the label.",
        application={
            "brand_name": "Two Rivers",
            "class_type": "Silver Rum",
            "alcohol_content": "40.5",
            "net_contents": "750 mL",
            "beverage_type": "distilled spirits",
        },
    ),
    LabelSpec(
        filename="07-spirits-missing-net-contents.png",
        brand_name="OLD SEXTANT",
        class_type="Barrel Aged Rum",
        alcohol_content="43% Alc./Vol. (86 Proof)",
        net_contents=None,
        warning=WARNING_STATEMENT,
        beverage_type="distilled spirits",
        notes="Defect: net contents absent from the artwork.",
        application={
            "brand_name": "Old Sextant",
            "class_type": "Barrel Aged Rum",
            "alcohol_content": "43",
            "net_contents": "750 mL",
            "beverage_type": "distilled spirits",
        },
    ),
    LabelSpec(
        filename="08-spirits-proof-inconsistent.png",
        brand_name="FIVE FATHOMS",
        class_type="Straight Bourbon Whiskey",
        alcohol_content="45% Alc./Vol. (92 Proof)",
        net_contents="750 mL",
        warning=WARNING_STATEMENT,
        beverage_type="distilled spirits",
        notes="Defect: 92 proof is not twice 45 percent; the label contradicts itself.",
        application={
            "brand_name": "Five Fathoms",
            "class_type": "Straight Bourbon Whiskey",
            "alcohol_content": "45",
            "net_contents": "750 mL",
            "beverage_type": "distilled spirits",
        },
    ),
    LabelSpec(
        filename="09-wine-clean.png",
        brand_name="HOLLOW CREEK",
        class_type="Napa Valley Cabernet Sauvignon",
        alcohol_content="13.5% Alc./Vol.",
        net_contents="750 mL",
        warning=WARNING_STATEMENT,
        producer="Produced and bottled by the named winery",
        beverage_type="wine",
        notes="Clean wine label. No proof statement, so no proof cross-check applies.",
        application={
            "brand_name": "Hollow Creek",
            "class_type": "Napa Valley Cabernet Sauvignon",
            "alcohol_content": "13.5%",
            "net_contents": "750 mL",
            "beverage_type": "wine",
        },
    ),
    LabelSpec(
        filename="10-wine-cross-unit-net-contents.png",
        brand_name="QUIET ORCHARD",
        class_type="Willamette Valley Pinot Gris",
        alcohol_content="12.5% Alc./Vol.",
        net_contents="750 mL",
        warning=WARNING_STATEMENT,
        producer="Produced and bottled by the named winery",
        beverage_type="wine",
        notes="Defect: the application states net contents in fluid ounces, the label in mL.",
        application={
            "brand_name": "Quiet Orchard",
            "class_type": "Willamette Valley Pinot Gris",
            "alcohol_content": "12.5",
            "net_contents": "25.4 fl oz",
            "beverage_type": "wine",
        },
    ),
    LabelSpec(
        filename="11-beer-rotated.png",
        brand_name="NORTH SPUR",
        class_type="India Pale Ale",
        alcohol_content="6.2% Alc./Vol.",
        net_contents="12 fl oz",
        warning=WARNING_STATEMENT,
        producer="Brewed and bottled by the named brewery",
        beverage_type="malt beverage",
        rotate_degrees=4.0,
        notes="Image defect: photographed at an angle. Jenny Park's weird angles case.",
        application={
            "brand_name": "North Spur",
            "class_type": "India Pale Ale",
            "alcohol_content": "6.2",
            "net_contents": "12 fl oz",
            "beverage_type": "malt beverage",
        },
    ),
    LabelSpec(
        filename="12-beer-low-contrast.png",
        brand_name="GREY HARBOR",
        class_type="Bohemian Style Pilsner",
        alcohol_content="4.8% Alc./Vol.",
        net_contents="12 fl oz",
        warning=WARNING_STATEMENT,
        producer="Brewed and bottled by the named brewery",
        beverage_type="malt beverage",
        low_contrast=True,
        notes="Image defect: poor contrast. Jenny Park's bad lighting case.",
        application={
            "brand_name": "Grey Harbor",
            "class_type": "Bohemian Style Pilsner",
            "alcohol_content": "4.8",
            "net_contents": "12 fl oz",
            "beverage_type": "malt beverage",
        },
    ),
]
