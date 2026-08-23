# Dependency triage, August 2026

Triage of the twelve Dependabot pull requests opened against `develop` on
2026-08-22, the first run after the repository was initialized.

**Nothing was merged or closed by the triage itself.** The table below is
recommendations for the repository owner. What was actually done with them, and
what has happened since, is recorded in "What happened after this triage" near
the end. The policy change that follows from the triage is in
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

## Second Dependabot run, 2026-08-22

Three more pull requests, all npm, all against `frontend/package.json`. Same
rule as above: the recommendation turns on what was actually exercised, and
**nothing here was merged or closed.**

| PR | Bump | Kind | CI | Recommendation |
| --- | --- | --- | --- | --- |
| [#43](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/43) | `typescript` 5.7.3 to 5.9.3 | npm, minor | Green, run 32595217249 | **Merge**, then regenerate the lock file |
| [#44](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/44) | `@eslint/js` 9.39.5 to 10.0.1 | npm, major | **Red**, run 32595220178 | **Merge only together with #42** |
| [#42](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/42) | `eslint` 9.39.5 to 10.8.1 | npm, major | **Not run**; conflicts with `develop` | **Merge only together with #44** |

### #43, typescript 5.9.3: merge

**It edits the manifest, and it has to.** `frontend/package.json` pins
`"typescript": "~5.7.2"`. A tilde range admits patch releases only, so 5.9.3 is
outside it and Dependabot cannot deliver this bump by resolution alone; the
declared range had to move. The pull request changes exactly that one line,
`~5.7.2` to `~5.9.3`, and nothing else.

**The peer range admits it.** `typescript-eslint@8.67.0` declares
`peer typescript ">=4.8.4 <6.1.0"`. 5.9.3 is inside that window, which is the
whole difference between this and #36: TypeScript 7.0.2 fell outside the same
range and could not resolve a tree at all. Here npm resolved normally and all
four jobs are green, including `tsc -b` in the frontend build. That is real
evidence, not a version-number judgement, because the compiler actually ran.

**One condition on merging it.** The lock file pins `typescript@5.7.3`.
Merging #43 changes `package.json` without changing `package-lock.json`, and
once the lock file is on `develop` that combination is exactly what `npm ci`
refuses. So either regenerate the lock on `develop` immediately after merging,
or merge it before pull request #45 and let #45 be rebased onto it. Doing
neither leaves `develop` red.

### #42 and #44, eslint 10: one change or neither

These are the same upgrade split across two pull requests, and the split is why
#44 fails. `eslint` and `@eslint/js` are published together from the same
repository at the same version, and `@eslint/js` declares a peer dependency on
the matching `eslint` major. Raising one alone cannot resolve. CI proves it, on
run 32595220178:

```
npm error code ERESOLVE
npm error While resolving: @eslint/js@10.0.1
npm error Found: eslint@9.39.5
npm error   dev eslint@"^9.17.0" from the root project
npm error Could not resolve dependency:
npm error peerOptional eslint@"^10.0.0" from @eslint/js@10.0.1
npm error Conflicting peer dependency: eslint@10.9.0
```

Three of the four jobs fail, each at its `npm install` step, and none of them
ever ran ESLint. This says nothing about whether eslint 10 works here; it says
`@eslint/js` 10 alone does not install.

**Every plugin in the tree already declares eslint 10 support.** Read from the
resolved `package-lock.json`, so these are the ranges the installed versions
actually publish:

| Package | Version | Declared `eslint` peer range | Admits 10 |
| --- | --- | --- | --- |
| `typescript-eslint` | 8.67.0 | `^8.57.0 \|\| ^9.0.0 \|\| ^10.0.0` | yes |
| `eslint-plugin-react-hooks` | 7.1.1 | `^3.0.0 \|\| ... \|\| ^9.0.0 \|\| ^10.0.0` | yes |
| `eslint-plugin-react-refresh` | 0.5.4 | `^9 \|\| ^10` | yes |

`@typescript-eslint/eslint-plugin`, `parser` and `utils` at 8.67.0 declare the
same range as their umbrella package. So there is no known peer-range obstacle
to eslint 10, which is the opposite of the situation with #36 and #28.

**#42 also conflicts with `develop` and has never run CI.** `git merge-tree`
against `develop` reports `CONFLICT (content): Merge conflict in
frontend/package.json`: the branch was cut before #32, #34 and #35 changed
adjacent lines in the same `devDependencies` block. It needs
`@dependabot rebase` before it can be evaluated at all.

**Recommendation: merge the two together, as one change, once it has been run
as one change.** Not close: closing would discard an upgrade that every
declared peer range says is available, and the only failure on record is the
artefact of proposing half of it. Not merge-as-is either: two pull requests
cannot be merged simultaneously, and merging either one first puts `develop` in
the broken state #44 already demonstrated.

The way to take it is a single pull request that raises `eslint` and
`@eslint/js` together and regenerates `package-lock.json` in the same commit,
after #45 lands. CI on that pull request runs `npm ci` against the combined
tree and then runs ESLint over the codebase, which is the evidence that is
missing today. **That evidence does not exist yet**, and it is the reason this
is a recommendation rather than a decision: the peer ranges say the tree should
resolve, but no run has resolved it. It could not be produced from the session
that wrote this, because `registry.npmjs.org` is denied there (OQ-15), so npm
could not be asked to resolve anything locally.

**No ignore entries were added for `eslint` and `@eslint/js`.** The coupled
ignore treatment given to `vite` and `@vitejs/plugin-react` fits a pair that is
known to be unadoptable; this pair is not. Adding it would hide the linter from
updates on the strength of a failure that is explained by the split rather than
by incompatibility. If the combined pull request above turns out red, that
changes, and the ignore group is the right answer then, with the failure quoted
as the reason.

## The eslint 10 evidence, 2026-08-23

The second-run triage above recommended eslint 10 as "one change or neither" and
said the evidence for it did not exist, because `registry.npmjs.org` was denied
in the session that wrote it (OQ-15). **OQ-15 is now closed and the evidence
exists.** It was produced on `feature/eslint-10-evaluation`, which raises
`eslint` and `@eslint/js` to `^10.0.0` together in `frontend/package.json` and
regenerates `frontend/package-lock.json` in the same commit.

**Verdict: green. Recommend closing #42 and #44 in favour of the combined pull
request.**

Every step of the `frontend lint and build` job and the npm half of
`dependency audit`, run against the combined tree:

| Step | Result |
| --- | --- |
| `npm ci --no-audit --no-fund` | 159 packages, no ERESOLVE |
| `npm run lint` (`eslint .`) | Clean, no errors and no warnings |
| `npm run format:check` (`prettier --check`) | All matched files use Prettier code style |
| `npm run build` (`tsc -b && vite build`) | 29 modules transformed, built in 975 ms |
| `npm audit --audit-level=high` | found 0 vulnerabilities |

The resolved tree confirms what the peer ranges predicted. Every plugin
deduplicates onto the single `eslint@10.9.0`:

```
+-- @eslint/js@10.0.1
| `-- eslint@10.9.0 deduped
+-- eslint-plugin-react-hooks@7.1.1
| `-- eslint@10.9.0 deduped
+-- eslint-plugin-react-refresh@0.5.4
| `-- eslint@10.9.0 deduped
+-- eslint@10.9.0
`-- typescript-eslint@8.67.0
  +-- @typescript-eslint/eslint-plugin@8.67.0
  +-- @typescript-eslint/parser@8.67.0
  +-- @typescript-eslint/utils@8.67.0
  `-- eslint@10.9.0 deduped
```

**No flat-config change was needed.** `frontend/eslint.config.js` is unmodified.
This was the open risk in the recommendation: peer ranges only promise that a
tree resolves, not that the config still parses or that the rules still exist.
Both held.

**The lock regeneration touched the eslint tree and nothing else.** `typescript`
stays at 5.7.3, `typescript-eslint` at 8.67.0, `vite` at 6.4.3, `react` at
19.2.8, `prettier` at 3.9.6 and `globals` at 17.11.0. The diff is 99 insertions
against 348 deletions, which is eslint 10 carrying fewer transitive dependencies
than eslint 9 did: `@eslint/eslintrc` and its `js-yaml`, `chalk`, `import-fresh`
and `strip-json-comments` subtree are gone, which is the eslintrc compatibility
layer eslint 10 dropped.

**One thing worth recording that the triage did not anticipate.** The lock entry
being replaced carried a deprecation notice:

```
"deprecated": "This version is no longer supported. Please see
https://eslint.org/version-support for other options."
```

So `develop` is currently pinned to an eslint version upstream has stopped
supporting. That does not change the verdict, but it moves this from an optional
upgrade to one with a reason to take it.

**What to do with #42 and #44.** Close both, unmerged, citing the combined pull
request. #42 also conflicts with `develop` and has never run CI; #44 is red for
the reason the triage identified, which is that it is half of an upgrade. Neither
carries a lock file, so merging either as it stands would leave `develop` red
until the lock was regenerated. The combined pull request carries both files and
has been run as one change, which is what the recommendation asked for.

**No coupled ignore group was added for `eslint` and `@eslint/js`.** The second
run's triage said an ignore group would be the right answer only if the combined
change turned out red. It did not, so the pair stays eligible for updates. The
`vite` and `@vitejs/plugin-react` treatment fits a pair known to be unadoptable;
this pair is now known to be adoptable, which is the opposite finding.

### #43, typescript 5.9.3: the rebase could not be triggered from a session

**#43 is still un-rebased, and it is still `package.json` only.** Head
`33491641`, one file changed, based on `d405786`, which predates the merges of
#45 and #46. Merging it as it stands would leave `develop` red until the lock
file was regenerated, exactly as the "Lock file interaction" section below says.

A rebase comment was posted to #43 on 2026-08-23 and **Dependabot did not
receive it**. The session's GitHub tooling rewrites bot mentions before posting,
inserting `U+00B7` middle dots into the mention and into the command word. The
comment landed on the pull request reading:

```
·@·d·ependabot r·ebase
```

That is a deliberate guardrail against an agent driving another automation, not
a bug to work around, and no attempt was made to evade it. Recorded as
[OQ-19](OPEN_QUESTIONS.md#oq-19).

**Three alternatives were considered and rejected.**

- **Use the "Update branch" button** (merge `develop` into the pull request).
  This makes #43 red rather than green. It would bring `develop`'s lock file in,
  which still pins `typescript` 5.7.3, against a `package.json` asking for
  5.9.3. `npm ci` refuses a lock that disagrees with its manifest, so all three
  npm jobs would fail at install.
- **Push a regenerated lock to Dependabot's branch.** Dependabot states in the
  pull request body that it resolves conflicts "as long as you don't alter it
  yourself", so a manual push takes the pull request out of its management. It
  is also someone else's branch.
- **Recreate the bump by hand on a new branch.** That produces a pull request
  Dependabot does not know about, and leaves #43 open to be closed manually
  anyway. It trades one manual step for two.

**So it stays a manual step for the repository owner:** comment
`@dependabot rebase` on #43. Dependabot then regenerates
`frontend/package-lock.json` as part of the pull request, which is the clean
order for all three of #42, #43 and #44.

Note the interaction if both #43 and the eslint change land: both regenerate the
same lock file, so whichever merges second needs a rebase, for the same reason as
everything else in the "Lock file interaction" section below.

**Nothing here was merged.**

## Lock file interaction, from 2026-08-22 onward

Every recommendation above has an extra step now that it did not have when the
first triage was written, because both ecosystems build from committed lock
files (OQ-3, pull request #45).

**A merged bump that changes only the manifest leaves `develop` red.** This is
not a subtle drift; it is a hard stop, and it is deliberate:

- `npm ci` refuses to run when `package.json` and `package-lock.json` disagree,
  and the frontend job, the audit job and the container build all begin with it.
- `pip install --require-hashes` refuses an entry whose digest is missing or
  does not match.

So a Dependabot pull request has to either carry its lock file change or be
followed by a regeneration commit. Which applies depends on when the branch was
cut:

- **Pull requests Dependabot opens from now on** will carry it. Dependabot
  updates `package-lock.json` itself whenever a lock file exists on the base
  branch, so once #45 merges, its npm pull requests contain both files.
- **#42, #43 and #44 will not**, because all three were branched from a
  `develop` that had no lock file. Each changes `package.json` only. Merging any
  of them as they stand, after #45, breaks `develop` until the lock is
  regenerated. Rebasing them first (`@dependabot rebase`) makes Dependabot
  regenerate the lock as part of the pull request, which is the cleaner order.
- **The pip ecosystem never carries it**, because `requirements.lock` and
  `requirements-dev.lock` are pip-compile output that Dependabot does not
  generate. A merged pip bump raises a floor in `pyproject.toml` and both lock
  files must be regenerated by hand afterwards, per
  [CONTRIBUTING.md](../CONTRIBUTING.md).

The rule this reduces to is in `CONTRIBUTING.md`: **any pull request that
changes `frontend/package.json` or `backend/pyproject.toml` regenerates the
affected lock file in the same pull request.** It applies to Dependabot's pull
requests exactly as it applies to everyone else's.

## What this triage does not cover

- **The eslint 10 result is a scaffold result.** `eslint .` over a Vite scaffold
  with one component exercises very little of what a linter does. It proves the
  toolchain installs, the flat config parses and the rules load; it does not
  prove that eslint 10 is quiet over the application code, because there is
  barely any. That is the same caveat this document applies to every frontend
  toolchain bump, and it applies here too.
- **No lockfile existed when these recommendations were written** (OQ-3), so
  none of them was reproducible: resolving the same declared ranges tomorrow
  could produce a different tree. Both lock files have since been committed and
  OQ-3 is closed, so dependency review from here on has something fixed to
  review. That does not retroactively make the table above reproducible.
- **`npm audit` and `pip-audit` results are not restated here.** Both run in
  the `dependency audit` CI job on every pull request, and both are green on
  `develop` at `ef3086a`. This document is about update policy, not
  vulnerabilities.
