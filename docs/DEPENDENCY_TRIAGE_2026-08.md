# Dependency triage, August 2026

Triage of the twelve Dependabot pull requests opened against `develop` on
2026-08-22, the first run after the repository was initialized.

**Nothing in this document was merged or closed.** These are recommendations
for the repository owner. The policy change that follows from them is in
[.github/dependabot.yml](../.github/dependabot.yml).

Author: Kimberly D. Kight. Date: 2026-08-22.

## Context

Ten of the twelve are major bumps. That is not Dependabot misbehaving; it is
what a first run looks like against a repository whose dependency floors were
written by hand and then relaxed to security minimums rather than pinned to
current releases. Two of the twelve fail CI, and both fail the same way: `npm
install` cannot resolve a dependency tree, so the failure happens before any
code is compiled or linted.

The repository state that shapes every recommendation below:

- **There is no application code yet.** The frontend is a Vite scaffold with
  essentially one component; the backend exposes `GET /api/health` only. CI
  passing on a frontend toolchain bump is therefore weak evidence. It says the
  scaffold still builds, not that the application still works.
- **There is no lockfile in either ecosystem** (OQ-3). Merging any npm bump
  changes only the declared range; the resolved tree is still whatever the
  registry serves that day.
- **The deploy workflow is disabled**, every job carrying `if: false`, and no
  AWS infrastructure exists (OQ-13). Actions used only there are never
  exercised by CI.

## Triage table

| PR | Bump | Kind | CI | Recommendation | Reason |
| --- | --- | --- | --- | --- | --- |
| [#25](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/25) | `python` 3.11-slim-bookworm to 3.14-slim-bookworm | Docker, major | Green | **Close** | Splits the tested runtime from the shipped one. CI runs pytest on 3.11 (`ci.yml` pins `python-version: "3.11"`); this would ship 3.14 in the container. Green CI here only proves the image builds and answers `/api/health`. |
| [#26](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/26) | `node` 22-bookworm-slim to 26-bookworm-slim | Docker, major | Green | **Close** | Same split in the other direction: `ci.yml` pins `node-version: "22"` for the frontend job, so the tested Node and the build-image Node would differ by four majors. |
| [#27](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/27) | `aws-actions/configure-aws-credentials` 4 to 6 | Action, major | Green | **Hold** | Used only in `deploy.yml`, where every job is `if: false`. CI green means this action never ran. Merging an unexercised two-major credential-handling bump buys false confidence. Take it as part of the deployment task, where it can actually be run. |
| [#28](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/28) | `vite` 6.4.3 to 8.2.1 | npm, major | **Red** | **Close** | `npm error ERESOLVE`: `@vitejs/plugin-react@4.7.0` declares `peer vite "^4.2.0 \|\| ^5.0.0 \|\| ^6.0.0 \|\| ^7.0.0"`. Vite 8 is outside it. Unadoptable until the React plugin ships a Vite 8 peer range. |
| [#29](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/29) | `docker/build-push-action` 6 to 7 | Action, major | Green | **Merge** | The container job on this very pull request used the new version to build the image, run the health probe, assert non-root, and generate the SBOM. The bump is verified by the run that reports it green. |
| [#30](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/30) | `actions/upload-artifact` 4 to 7 | Action, major | Green | **Merge** | Same: the SBOM artifact uploaded successfully under v7 in this run. |
| [#31](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/31) | `actions/setup-node` 4 to 7 | Action, major | Green | **Merge** | Exercised twice in the run, by the frontend job and the audit job, both green. |
| [#32](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/32) | `eslint-plugin-react-refresh` 0.4.26 to 0.5.4 | npm, minor | Green | **Merge** | The only non-major in the set. Dev-only lint plugin, lint green. Note it is a `0.x` package, where a minor can still break, which is why it was read rather than waved through. |
| [#33](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/33) | `actions/checkout` 4 to 7 | Action, major | Green | **Merge** | Exercised by all four jobs in this run, all green. |
| [#34](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/34) | `globals` 15.15.0 to 17.11.0 | npm, major | Green | **Merge** | Despite two majors, this package is a data file of global identifier names consumed by the ESLint config. Its majors are removals of obsolete environments. Lint green is meaningful evidence for this one, because linting is the only thing it feeds. |
| [#35](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/35) | `eslint-plugin-react-hooks` 5.2.0 to 7.1.1 | npm, major | Green | **Merge, with a caveat** | Lint-only, and green. The caveat is that v6 introduced the React Compiler rule set, so this is stricter than v5 on real hook usage, and there is almost no hook usage here to be strict about. Expect new findings when FR-1 components land; those will be legitimate, not regressions from this merge. |
| [#36](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/36) | `typescript` 5.7.3 to 7.0.2 | npm, major | **Red** | **Close** | Diagnosed in full below. |

Totals: **six recommended merge**, one merge with a caveat included; **four
recommended close**; **one hold**; **zero merged or closed by this triage**.

## Why #36 fails, and what adopting TypeScript 7 would require

**The failure is dependency resolution, not compilation.** Three of the four
jobs fail, and each fails at its `npm install` step with the same error:

```
npm error code ERESOLVE
npm error ERESOLVE unable to resolve dependency tree
npm error While resolving: ttb-label-verifier-frontend@0.1.0
npm error Found: typescript@7.0.2
npm error node_modules/typescript
npm error   dev typescript@"~7.0.2" from the root project
npm error
npm error Could not resolve dependency:
npm error peer typescript@">=4.8.4 <6.1.0" from typescript-eslint@8.67.0
npm error node_modules/typescript-eslint
npm error   dev typescript-eslint@"^8.18.0" from the root project
```

`typescript-eslint@8.67.0`, which `frontend/package.json` requests as
`^8.18.0`, declares a peer dependency of `typescript ">=4.8.4 <6.1.0"`.
TypeScript 7.0.2 is outside that range, so npm refuses to build a tree.

Two consequences worth stating plainly:

- **Not a single line of TypeScript was type-checked.** `tsc -b` never ran.
  Whether this codebase compiles under TypeScript 7 is unknown, and this run
  says nothing about it either way.
- **The `backend lint and test` job passed**, which is the tell that this is an
  npm-tree problem rather than anything to do with the change itself. The other
  three jobs fail only because each begins with `npm install`.

**What adopting TypeScript 7 would require**, in order:

1. **Wait for `typescript-eslint` to publish a major whose peer range admits
   TypeScript 7**, then raise the `typescript-eslint` floor in
   `frontend/package.json` in the same change as the TypeScript bump. This is
   the blocking step and it is not in this repository's control.
2. **Check `@vitejs/plugin-react` and `vite` peer ranges** in the same pass.
   PR #28 shows the frontend already has one peer-range conflict pending, and
   resolving TypeScript without resolving Vite produces a second unresolvable
   tree.
3. **Run `tsc -b` and read the errors.** TypeScript 7 is the native-port
   compiler line; it is expected to be stricter and faster, and any errors it
   raises are real findings in the code rather than noise to suppress.
4. **Do it against real components, not the scaffold.** A green `tsc` over one
   file proves nothing about a codebase that does not exist yet.

**What must not be done:** `--force` or `--legacy-peer-deps`, which npm itself
suggests in the error text. Both would install a tree npm has just said is
incorrect, and the lint toolchain would then be running against a compiler
version its authors have not tested. That converts a loud, early failure into
a quiet one.

Because step 1 is out of our hands and steps 2 to 4 belong to the frontend work
that has not started, **the recommendation is close rather than hold**. Holding
implies waiting on something small. This is waiting on an upstream release and
then a real piece of work, and it should be reopened deliberately when both are
true. The `ignore` entry added to `.github/dependabot.yml` stops Dependabot
reopening it weekly in the meantime.

## Policy change

[.github/dependabot.yml](../.github/dependabot.yml) is updated to:

1. **Group minor and patch updates** into one pull request per ecosystem per
   week, across all four ecosystems. Major bumps stay ungrouped, because a
   major is a decision and a decision deserves its own pull request, its own CI
   run, and its own recorded reason.
2. **Ignore major bumps of `typescript` and `react`** in the npm ecosystem, for
   the reasons above and because there is no UI to regression-test a React
   major against yet.

Grouping is the change that matters most here. Eight of these twelve pull
requests would have been three grouped ones under the new policy, and the four
that genuinely needed a decision would have been visible instead of buried.

**The gap this triage left open is now closed.** The triage named `typescript`
and `react` and did not name `react-dom`, even though the two must move
together, so Dependabot could still open a `react-dom` major on its own that
nobody could merge alone. `react-dom` has since been added to the same ignore
block.

The same coupling turned out to apply to the build tooling, and there the
evidence arrived rather than being predicted. See "What happened after this
triage" below.

## What happened after this triage

Recorded 2026-08-22, after the recommendations above were acted on.

**Acted on as recommended.** #29, #30, #31, #32, #33, #34 and #35 were merged.
#25, #26 and #28 were closed with the reasons given above. #36 was closed by
Dependabot itself once the `typescript` ignore rule was in place, which is the
rule working as intended.

**#41 is new evidence, and it completes a deadlock.** Dependabot opened
[#41](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/41),
`@vitejs/plugin-react` 4 to 6. It was closed, because plugin 6 requires a Vite
major this repository has not taken.

Read together with #28, the two closures are the same wall approached from
opposite sides:

| Pull request | Bump | Why it could not be merged |
| --- | --- | --- |
| #28 | `vite` 6.4.3 to 8.2.1 | `@vitejs/plugin-react@4.7.0` declares `peer vite "^4.2.0 \|\| ^5.0.0 \|\| ^6.0.0 \|\| ^7.0.0"`. Vite 8 is outside it, so `npm install` fails with ERESOLVE. Needs the plugin major first. |
| #41 | `@vitejs/plugin-react` 4 to 6 | Plugin 6 requires a Vite major. Needs the Vite major first. |

Neither half is mergeable alone, so any pull request that proposes one half can
only be closed. `vite` and `@vitejs/plugin-react` are therefore ignored at the
major level as a coupled pair. The upgrade is one change that raises both at
once, taken deliberately, with `tsc -b` and `vite build` read afterwards, and it
belongs with the frontend work that has not started. Removing both ignore
entries together is what reopens it.

**#27 stays open, and the condition for closing it is now written down.**
[#27](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/27),
`aws-actions/configure-aws-credentials` 4 to 6, was recommended **Hold** above
and is still open. Nothing has changed that would justify merging or closing it:

- The action is used only in `deploy.yml`, where every job still carries
  `if: false`. CI green on that pull request still means the action never ran.
- No AWS infrastructure exists yet (OQ-13), so there is nothing for it to
  authenticate against even if the jobs were enabled.
- It is a two-major bump of the step that handles credentials. That is the last
  place to accept a change verified only by the fact that nothing executed it.

**It stays open until `deploy.yml` is enabled.** Not closed, because unlike #25,
#26, #28, #36 and #41 there is nothing wrong with the bump: it is a routine
update of a maintained action, waiting only for a workflow that can exercise it.
Closing it would discard a valid update and invite Dependabot to reopen it every
week; ignoring it would hide a credential-handling action from updates
altogether, which is the opposite of what should happen. Holding an open pull
request is the accurate state, and it is cheap: one pull request, visible,
labelled, with the reason recorded here.

**Whoever enables the deployment workflow takes it in the same task**, together
with any changes the two majors require to the `deploy.yml` step, and confirms
it by a run that actually assumes a role rather than by a green check on a
skipped job.

## What this triage does not cover

- **No lockfile existed when these recommendations were written** (OQ-3), so
  none of them was reproducible: resolving the same declared ranges tomorrow
  could produce a different tree. Both lock files have since been committed and
  OQ-3 is closed, so dependency review from here on has something fixed to
  review. That does not retroactively make the table above reproducible.
- **`npm audit` and `pip-audit` results are not restated here.** Both run in
  the `dependency audit` CI job on every pull request, and both are green on
  `develop` at `ef3086a`. This document is about update policy, not
  vulnerabilities.
