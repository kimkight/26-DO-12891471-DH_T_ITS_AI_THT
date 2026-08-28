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

## Docker base images, 2026-08-23

Dependabot's fourth run produced
[#47](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/47), a
grouped docker `minor-and-patch` pull request that carried
`python:3.11-slim-bookworm` to `python:3.14-slim-bookworm`. It was closed. The
bump itself is the one already refused as
[#25](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/25), for
the reason recorded in the triage table above: `ci.yml` pins
`python-version: "3.11"`, so merging it would test on 3.11 and ship 3.14, and a
green container job proves only that the image builds and answers
`/api/health`.

**What is new is how it arrived.** #25 was an ungrouped major, which the policy
in point 1 of `dependabot.yml` deliberately keeps separate so that a runtime
change gets its own pull request and its own recorded decision. #47 was a
grouped pull request titled as a minor-and-patch update. The grouping rule did
not fail; the version reading underneath it did.

**Docker tags are not semver.** Dependabot parses a tag as though it were, and
the two base images fall on opposite sides of that:

| Image | Bump | How Dependabot reads it | Caught by `semver-major`? |
| --- | --- | --- | --- |
| `node` | `22-bookworm-slim` to `26-bookworm-slim` | major 22 to major 26 | Yes |
| `python` | `3.11-slim-bookworm` to `3.14-slim-bookworm` | minor 11 to minor 14, major 3 unchanged | **No** |

`python:3.14` is a new CPython release line, and CPython's own release process
calls 3.14 a major release. Nothing in the tag says so in semver terms. An
ignore entry written only as `version-update:semver-major` would therefore have
left #47 free to be reopened on the next weekly run, which is the failure this
section exists to prevent rather than to describe.

**The policy change.** The docker ecosystem now carries an `ignore` block:
`python` is ignored for both `version-update:semver-major` and
`version-update:semver-minor`; `node` is ignored for `version-update:semver-major`
only. The asymmetry is not an oversight, it is the table above.

Patch updates are still proposed for both images, so a rebuilt base carrying
security fixes inside the pinned line still arrives on its own schedule. That
is the update the weekly cadence is for, and nothing here suppresses it.

**What this does not do.** It does not pin the base images by digest; that TODO
is still in the `Dockerfile` and still owed before the first tagged release.
It also does not decide the runtime lines. Taking `python:3.14` or `node:26` is
a task: narrow or remove the matching ignore entry, move the matching `ci.yml`
pin in the same pull request so the tested runtime and the shipped runtime stay
one version, and read the test run rather than the health probe.

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

## #27 is superseded, 2026-08-24

`deploy.yml` is enabled. Every job's `if: false` is gone, the workflow runs on
`workflow_dispatch` and on a published release, and the infrastructure it
targets exists as Terraform in `infra/terraform/` (OQ-13 is closed). The
condition written down above, "it stays open until `deploy.yml` is enabled",
has been met.

**The v6 bump was taken directly in that change**, not by merging
[#27](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/27).
`deploy.yml` now pins `aws-actions/configure-aws-credentials@v6` at both places
it authenticates. That is the same version #27 proposes, arrived at in the task
that also wrote the trust policy the action assumes into, which is what the
triage asked for: the bump reviewed alongside a workflow that can exercise it,
rather than alongside a skipped job.

**Recommendation: close #27 as superseded.** Not merged, because there is
nothing left to merge; the file on `develop` will already be at v6 once this
branch lands, and Dependabot closes its own pull request when the target
version is reached. Closing it by hand is the tidier version of the same
outcome.

**What is still owed, and it is the part that matters.** The triage's last
sentence asked for confirmation "by a run that actually assumes a role rather
than by a green check on a skipped job." That has **not** happened. No AWS
account has been touched from any session in this project, so v6 has still
never authenticated against anything. The first run of the deploy workflow is
the confirmation, and it is the author's to run.

Concretely, what to watch on that first run: v5 and v6 of the action tightened
defaults around how the role session is named and how credentials are exported
to later steps. Nothing in `deploy.yml` depends on the loosened behaviour, and
`role-session-name` is set explicitly rather than left to the default, but a
first run is a first run. If it fails at the credential step, the failure is
readable and the fix is in the action's own release notes; it does not
implicate the Terraform.

**One row of the triage table above is now stale**, and rather than editing
history: the "Recommendation: Hold" against #27 was the right call at the time
and its condition has now been discharged here. The table stays as written,
because it is a record of what was decided on 2026-08-22 with what was known
then.

## Fifth Dependabot run: #56, `vitest` 3.2.7 to 4.1.11, 2026-08-24

One pull request, the second run after the interface landed in #54.
[#56](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/56) is a
dev-dependency major: `vitest` 3.2.7 to 4.1.11 in `frontend/package.json`.

**Recommendation: merge.** This is the first frontend major in this repository
that can be evaluated against something real, and it was evaluated rather than
waved through.

### The three questions the standing policy asks

**1. Does CI pass on the rebased tree?** Yes, and it was checked on the rebased
tree rather than on Dependabot's base. #56 was opened against `9a9bdad`;
`develop` is now `878a7f9`, one merge ahead. The only file that differs between
them is `README.md`, so the rebase is a formality, but the run below was done
on the current tree anyway rather than reasoning from that.

The pull request's own CI run is green on all five jobs
([run 32737017068](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/actions/runs/32737017068)).
Independently, with `frontend/package.json` and `frontend/package-lock.json`
from #56 applied to `878a7f9` and `npm ci` run from that lock:

| Check | Result |
| --- | --- |
| Resolved version | `vitest@4.1.11` |
| `npm run lint` | Clean |
| `npm run format:check` | "All matched files use Prettier code style" |
| `npm run build` (`tsc -b && vite build`) | 41 modules transformed, built |
| `npm run test` | **4 files, 61 tests, 61 passed** |
| `npm audit --audit-level=high` | 0 vulnerabilities |

Measured on a four-core Linux session container, Node 22.22.2, npm 10.9.7.

**2. Does the lock regenerate?** Yes, in the same pull request: 128 insertions
and 289 deletions across `package.json` and `package-lock.json`. `npm ci`
succeeds from it, which is the test that matters. The net shrink is the shape
of the change rather than noise: vitest 4 drops `vite-node`, `tinypool`,
`cac`, `loupe`, `deep-eql`, `check-error`, `pathval`, `tinyspy`, `sirv` and
its `@polka/url`, `mrmime` and `totalist`, `strip-literal`, `fflate`, and
`@vitest/ui`, and adds `obug` and `@standard-schema/spec`.

**3. Any breaking config change?** None that applies here, and this is where a
major deserves reading rather than a green check. `frontend/vitest.config.ts`
uses five options: `environment: 'jsdom'`, `globals: true`, `setupFiles`,
`include`, and `exclude`. All five survive v4 unchanged. What v4 removed or
reshaped, this repository does not use: no `workspace` (replaced by
`projects`), no `environmentMatchGlobs`, no `poolMatchGlobs`, no coverage
configuration, and no browser mode. Peer ranges hold: the repository is on
`vite ^6.0.0` and `@vitejs/plugin-react ^4.3.4`, and `npm ci` resolved without
an `ERESOLVE`, which is the failure mode #28 and #36 both hit.

### What this evidence is worth, and what it is not

**It is worth more than any previous frontend toolchain result in this
document.** Every earlier caveat here said the same thing: CI green on a Vite
scaffold with one component proves the toolchain installs, not that the
application works. That caveat has expired. There are 61 component tests over
the real interface now, covering outcome rendering as text and as shape and
colour, the live region, the timing line, the plain-language error path, the
batch table's sorting and status chips, and the results CSV. All 61 pass under
the new runner. That is a test-runner major evaluated by running the tests.

**Two things it is not.** First, `npm run test:a11y` was not run here: the
accessibility tier is Playwright against the built page and is a different
runner, untouched by this bump, and the pull request's own CI run covers it.
Second, `@vitest/ui` leaves the tree, so `vitest --ui` would need the package
added back. Nothing in this repository uses it: `test` is `vitest run` and
`test:watch` is plain `vitest`.

### One note on where this was written

This section is committed on `feature/us-17-terraform` rather than on a branch
of its own, against the usual one-branch-per-task rule. The reason is
mechanical: that branch already appends to this file for the #27 closure, and a
second branch appending to the same file would conflict for no benefit. #56
itself is untouched, and nothing here merges or closes it.

## Sixth Dependabot run: #67 and #68, 2026-08-28

Two pull requests, open and untouched since 2026-08-27. Both are triaged here
under the standing policy: does CI pass on the rebased tree, does the lock
regenerate, and is there a breaking configuration change. **Neither is merged
or closed by this triage.**

| PR | Bump | Kind | CI | Recommendation |
| --- | --- | --- | --- | --- |
| [#67](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/67) | `@types/react-dom` 19.2.4 to 19.2.5, in the minor-and-patch group | npm, patch, dev-only | Green, all six checks | **Merge** |
| [#68](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/68) | `hashicorp/setup-terraform` 3 to 4 | Action, major | Green, all six checks | **Merge** |

### #67: `@types/react-dom` 19.2.4 to 19.2.5

**A clean patch bump, and the recommendation is simply that.** It is a
DefinitelyTyped patch release of a type-only, development-only package: it
contributes no runtime code, ships nothing into the container, and cannot
change what the built page does. The three policy questions are answered
without a caveat worth writing at length.

**1. Does CI pass?** Yes, on the pull request's own run
([run 33068111814](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/actions/runs/33068111814)), all six checks green.
Independently, with the bump applied on top of this session's branches, which
is the tree it will actually land on rather than the one it was opened
against:

| Check | Result |
| --- | --- |
| Resolved version | `@types/react-dom@19.2.5` |
| `npm ci` from the regenerated lock | Succeeds |
| `npm run lint` | Clean |
| `npm run format:check` | "All matched files use Prettier code style" |
| `tsc -b --force` | Clean, which is the check that matters for a types-only bump |
| `npm run build` | Built |
| `npm run test` | 141 tests, 141 passed |
| `npm run test:a11y` | 12 tests, 12 passed |
| `npm audit --audit-level=high` | 0 vulnerabilities |

Measured on a four-core Linux session container, Node 22.22.2.

**2. Does the lock regenerate?** Yes, in the pull request: five insertions and
five deletions across `frontend/package.json` and `frontend/package-lock.json`.
The lock diff is the version, the resolved URL and the integrity hash of one
entry, plus the declared range. No transitive dependency is added or removed.

**3. Any breaking configuration change?** None. Nothing in the repository
configures this package; it is resolved by `tsc` through `@types` and consumed
by `react-dom`'s typings.

**One thing to do before merging, and it is about order rather than about the
bump.** This pull request was opened against `develop` at `417556a`, and this
session's `feature/modern-ui` branch also changes `frontend/package.json` and
`frontend/package-lock.json`, swapping the bundled typeface. Merging that first
makes #67 conflict on both files. The fix is one comment, `@dependabot rebase`,
and the bump is a single entry, so the rebase is mechanical. Merge the session's
branches first, then rebase and merge #67.

### #68: `hashicorp/setup-terraform` 3 to 4

**Merge.** This is a major bump of a CI action, and the case for it is the same
one that carried #29, #30, #31 and #33 in the first triage: the job on the pull
request that reports it green is the job that uses it.

**1. Does CI pass?** Yes, on the pull request's own run
([run 33068167766](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/actions/runs/33068167766)), all six checks green. The
one that counts is `infrastructure format and validate`, which is the only
place this action is used, in `.github/workflows/ci.yml`. That job ran
`terraform fmt -check -recursive -diff`, `terraform init -backend=false` and
`terraform validate` under the new version, with both of the inputs this
repository sets, and passed. This is not a green check on an unexercised
action, which is what made #27 a hold: it is the action doing its whole job.

**2. Does the lock regenerate?** Not applicable. An action reference is a git
ref, not a locked dependency; the change is one line, `@v3` to `@v4`.

**3. Any breaking configuration change?** None that reaches this repository,
and the one breaking change upstream is worth naming rather than waving past.
The release notes for v4.0.0, as quoted in the pull request, list exactly one:
**the action now requires Node.js 24 on the runner.** No input was removed or
renamed. This repository passes `terraform_version` and `terraform_wrapper`,
and the green `infra` job is direct evidence that both are still accepted.

The Node 24 requirement is a property of the runner rather than of the
configuration. CI runs on `ubuntu-latest`, GitHub-hosted, which supplies the
Node runtime a v4 action asks for, and the green run proves it did. **Where it
would bite is a move to a self-hosted or pinned older runner**, which this
repository does not have and would notice immediately if it did: the failure
would be the action refusing to start, named in the log, on the one job that
uses it.

**What this bump is not evidence about.** Terraform itself. The version this
repository installs is pinned at `1.13.3` in the workflow and is untouched by
the action bump. And `terraform validate` still means what it always meant
here: the configuration is well formed against the provider schema, checked
with `-backend=false` and no credentials. It does not mean an apply would
succeed, and nothing about moving to v4 changes that.

### Both, together

Neither pull request is blocked by anything in this session's work, and neither
blocks it. Recommended merge order: this session's three feature branches
first, because two of them change the files #67 touches; then `@dependabot
rebase` on #67; then #67 and #68 in either order. As with every other entry in
this document, **the merging is the repository owner's to do.**
