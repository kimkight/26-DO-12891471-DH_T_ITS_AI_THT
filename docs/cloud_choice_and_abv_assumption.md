# Cloud platform choice and the ABV tolerance assumption

> **Source record, not maintained.** This is the working note that ADR 0001,
> assumption A-12, and assumption A-13 were derived from. It is kept because
> those artifacts cite it as their source. It is not updated going forward; the
> maintained statements live in [adr/0001-cloud-platform-aws.md](adr/0001-cloud-platform-aws.md)
> and [ASSUMPTIONS.md](ASSUMPTIONS.md).

## 1. Why AWS, when Marcus said Azure

The honest record: when we planned this on 2026-08-20, I recommended Azure specifically because Marcus said TTB migrated to Azure in 2019, and you chose AWS because it is the platform you are most comfortable building and defending in an interview. That is a legitimate reason for a one-week take-home, but it is not what the repository currently says. Decision D-11 states that "the agency's intended production environment is AWS GovCloud (US)." No source supports that; Marcus's interview says Azure. D-11 as written is the one place in the repo where something was asserted rather than sourced, and it was my drafting error, not Claude Code's.

Does AWS still make sense? Yes, with the reasoning stated plainly instead of implied:

- The assignment says "You are free to use any programming languages, frameworks, or libraries you prefer" and Marcus says the prototype is "standalone," not integrated with COLA, and "could potentially inform future procurement decisions... years away." The prototype does not have to run inside TTB's Azure tenant.
- What must survive a platform change is the design, not the hosting: a single container image, Terraform with no provider-specific application logic, OCR in-process with no cloud ML dependency, and an optional vision fallback behind an interface. Moving from ECS Fargate to Azure Container Apps or AKS is a deployment change, not a rewrite. The firewall lesson from the vendor pilot is the reason the default path has no cloud API dependency at all, and that decision is what makes the platform swappable.
- Delivering a working, deployed prototype in the time available on the platform you know best is the better trade than delivering a half-working one on the platform that matches the agency. The assignment says exactly this: "A working core application with clean code is preferred over ambitious but incomplete features."
- Both platforms have FedRAMP High government regions (AWS GovCloud; Azure Government). The compliance story is equivalent; the portability statement should name Azure Government as the likely production target, not GovCloud.

**Public evidence (researched 2026-08-20):** Treasury's department-wide shared cloud, the Workplace Community Cloud (WC2), runs on commercial AWS at FedRAMP Moderate and High (WC2-M and WC2-H), operated through the OCIO with Booz Allen as integrator; Treasury stated an intent to add Azure to WC2 and in 2023 awarded SAIC the $1.3B T-Cloud broker contract covering AWS, Microsoft, Google, IBM, and Oracle. No public document states which provider TTB's own systems (COLAs Online, myTTB) run on; TTB's FY 2027 budget justification describes replacing COLAs Online with myTTB but names no cloud provider. So the real-world Treasury baseline is AWS-first and multicloud by policy; the "Azure since 2019" statement belongs to the assignment's fictional scenario and should be treated as stakeholder context, not verified fact. The ADR should say both things: the scenario's stakeholder says Azure, public Treasury evidence says AWS WC2 plus multicloud, and the design is portable to either.

What a reviewer will probe: "You read that we're on Azure and built on AWS. Why?" The answer above is defensible. The answer "I assumed GovCloud" is not, because it contradicts the interview. So fix the record.

### Changes to make in the repository

**D-11 (in docs and the charter), replace with:**
"D-11: Target environment. The agency states it is on Azure (Marcus Williams interview). This prototype deploys to AWS commercial us-east-1 by the author's choice, for delivery speed on the platform the author knows best, which the assignment permits. The architecture is container-first and cloud-portable by design; a production deployment would target the agency's platform, presumed to be Azure Government, and that would be a deployment change rather than a redesign. FedRAMP status of any target service is confirmed against the FedRAMP Marketplace at deployment time, not asserted here."

**ADR 0001, add a section "Why not Azure, given the agency runs Azure":** state the four points above as Context and Consequences, including the negative consequence: the prototype's infrastructure code does not exercise the agency's actual platform, so the Terraform would need an Azure provider module before a pilot. Mark OQ-1 as "Answered by ADR 0001 (author's decision, not a stakeholder answer)."

**NFR-10**, retitle from "Portability to AWS GovCloud (US)" to "Portability to a FedRAMP-authorized government region (AWS GovCloud or Azure Government)" and keep the same acceptance criteria.

**06_SECURITY_AND_COMPLIANCE.md**, wherever GovCloud is named as the production target, say "the agency platform (Azure per the interview); AWS GovCloud if AWS were retained."

## 2. ABV tolerance: the conservative assumption (closes OQ-4)

### What the regulations actually say

Fetched from eCFR on 2026-08-20:

- 27 CFR 5.65 (distilled spirits): "A tolerance of plus or minus 0.3 percentage points is allowed for actual alcohol content that is above or below the labeled alcohol content." https://www.ecfr.gov/current/title-27/section-5.65
- 27 CFR 4.36 (wine): tolerance of 1 percent for wines over 14 percent ABV, and 1.5 percent for wines at 14 percent or less, "either above or below" the stated percentage. https://www.ecfr.gov/current/title-27/section-4.36
- 27 CFR 7.65 (malt beverages): "a tolerance of 0.3 percentage points will be permitted, either above or below the stated alcohol content, for malt beverages containing 0.5 percent or more alcohol by volume." https://www.ecfr.gov/current/title-27/section-7.65

### Why those tolerances do not apply to this tool

Every one of those tolerances governs the difference between the **actual** alcohol content of the liquid and the **labeled** content. That is a laboratory question. This tool compares two **declared** values: what the applicant wrote on the label artwork and what the applicant typed into the application form. Both are the applicant's own statements of the same number. There is no regulatory basis for allowing them to differ, and Sarah's description of the check is "ABV is correct? Check," meaning the number on the form is the number on the label.

### Assumption A-12 (to add to ASSUMPTIONS.md and FR-7)

**A-12: Alcohol content on the label and in the application must be numerically identical.**

- Normalize both values before comparison: strip "%", "Alc./Vol.", "ABV", "alc. by vol.", whitespace, and trailing zeros, so `45% Alc./Vol.`, `45.0%`, and `45` are the same number.
- If the label also states proof, cross-check that proof equals 2 x ABV (27 CFR 5.65 defines proof this way for spirits). A proof value that does not equal twice the ABV is reported as **needs human review** with both numbers shown, because it indicates an internal inconsistency on the label itself.
- If the two normalized ABV numbers are equal: **match**.
- If they differ by any nonzero amount: **mismatch**, with both values and the difference shown. No tolerance band is applied. The agent can overrule; the tool does not.
- If either value cannot be parsed as a number: **needs human review**, with the raw strings shown, falling back to text comparison as FR-7 already requires.
- Range statements (for example "12 to 14% alc/vol", permitted for wine under 27 CFR 4.36): if the label states a range and the application states a single value, **needs human review**. The prototype does not evaluate range semantics.

**Why this is the conservative choice:** the only failure that harms the process is a false match, where the tool tells an agent two different numbers agree. Requiring exact equality makes a false match on this field impossible except through an OCR misread, and OCR confidence is shown alongside the value. The cost is false mismatches on OCR errors like `45` read as `46`, which land in front of an agent with both values visible, which is today's manual check anyway.

**What would change it:** a compliance agent or Sarah Chen stating that applications and labels are routinely accepted with small ABV differences. No source says so. Configurable `TTB_ABV_TOLERANCE` defaults to 0.0 so the behavior can change without a code change if that answer arrives.

**Traceability:** Source: Sarah Chen interview ("ABV is correct? Check"); 27 CFR 5.65, 4.36, 7.65 (fetched 2026-08-20) for why regulatory tolerances are out of scope; Decision D-5 (numeric comparison). Marks OQ-4 as closed by assumption A-12.

### Same treatment for OQ-5 (net contents), briefly

Compare numerically only when units match after normalization (`mL`/`ml`/`milliliters`, `L`/`liters`, `fl oz`/`fl. oz.`). Different units: **needs human review**, no conversion performed. Standards of fill are not validated. Record as A-13.

## 3. Claude Code prompt to apply these changes

Paste into a cloud session on a `feature/adr-0001-and-a12` branch from `develop`:

"Apply the following changes. Do not alter anything else. Source for every statement is the file `docs/cloud_choice_and_abv_assumption.md` which I am adding to the repo in this commit; cite it and the eCFR URLs it contains.
1. Replace the text of Decision D-11 wherever it appears (charter, architecture, security, ADR references) with the D-11 text in section 1 of that file.
2. Add a section to `docs/adr/0001-cloud-platform-aws.md` titled 'Why not Azure, given the agency runs Azure' using the four points and the negative consequence in section 1. Update ADR status to Accepted if it is not already.
3. Mark OQ-1 as 'Answered by ADR 0001 (author's decision, not a stakeholder answer)' in OPEN_QUESTIONS.md.
4. Retitle NFR-10 as stated; adjust 06_SECURITY_AND_COMPLIANCE.md references to GovCloud as stated.
5. Add A-12 and A-13 to ASSUMPTIONS.md verbatim from section 2; extend FR-7 acceptance criteria with the A-12 and A-13 rules; add `TTB_ABV_TOLERANCE=0.0` to `.env.example` and the configuration table; mark OQ-4 and OQ-5 closed by A-12 and A-13.
6. Add test cases to `docs/07_TEST_STRATEGY.md` UAT list: 45 vs 45.0% match; 45 vs 45.1 mismatch; 90 proof with 45% passes cross-check; 92 proof with 45% needs review; 750 mL vs 25.4 fl oz needs review.
7. Update TRACEABILITY_MATRIX.md rows for FR-7.
8. Open a PR to `develop` titled 'docs: record cloud platform rationale and ABV/net contents assumptions (ADR 0001, A-12, A-13)'. Do not merge."
