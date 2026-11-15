# RAAST PR Review (diff-scoped)

`raast.review` + `.github/workflows/pr-review.yml` form a pull-request
review gate for RTL quality. It runs the RAAST static rule engine
(RTL001-RTL017) over the files changed in a PR, but **reports only
findings that land on lines the PR actually changed** — and it keeps the
conversation tidy by maintaining a single review comment per PR that is
updated in place on every push.

```text
python3 -m raast.review --base origin/main [--path .] [--config PATH]
    [--fail-on P0|P1|P2|off] [--comment-out FILE] [--format markdown|github]
```

## The only-changed-lines policy

The `raast.diffscope` module parses `git diff -U0` output and, for each
changed file, extracts the added/modified line ranges of the NEW file
(inclusive `(start, end)` pairs taken from the `@@ -a,b +c,d @@` hunk
headers). Every finding outside those ranges is suppressed.

This is deliberate:

- A three-file PR in a 50k-line legacy repository does not turn into a
  wall of pre-existing debt.
- Authors are never blamed for code they did not touch.
- The gate is adoptable on day one in existing codebases: an empty diff
  always produces a "Passed" comment, even if the repo has older RTL
  problems.

Consequences: pre-existing problems are NOT reported here. For full
repository coverage run `raast scan` (see docs/cli-reference.md)
separately. Deleted files and binary files produce no ranges and are
skipped.

## Comment anatomy

The markdown comment always starts with the `<!-- raast-review -->`
marker; the poster uses it to find and update the existing comment.

```markdown
<!-- raast-review -->
## RAAST RTL Review

Scanned 1 changed file(s), 1 changed line range(s). Reporting only findings on lines changed in this PR.

### P1 — RTL004 · `src/components/Card.css` · line 2

**Issue:** text-align: left

**Suggested fix:** text-align: start

### Summary

| Severity | Count |
|---|---|
| P0 | 0 |
| P1 | 1 |
| P2 | 0 |

**Status:** Review required.

<sub>Comment is updated in place on every push. Rule reference: docs/cli-reference.md</sub>
```

Findings are grouped P0 first, then P1, then P2. The status line is
`Review required.` when any P0/P1 finding exists on changed lines, and
`Passed — no RTL issues on changed lines.` otherwise. A clean push still
emits the header and the Passed status so the comment replaces any
previous failing one.

## Using it in your repository

1. Copy `.github/workflows/pr-review.yml` into your repo
   (`.github/workflows/pr-review.yml`).
2. Adjust `--base` if your default branch is not what
   `origin/${{ github.base_ref }}` resolves to (it usually is: it names
   the PR target branch on the origin remote).
3. The workflow needs `pull-requests: write` (already declared) to post
   the comment; the `GITHUB_TOKEN` is passed as `GH_TOKEN` for `gh api`.
4. Optional: commit a `raast.config.json` at the repo root to set the
   language profile (`fa`/`ar`/`he`/`es`), rule options and severity
   overrides — the review auto-discovers it.

## Making it merge-blocking

By design this workflow does not block merges by itself; it reports.
Two ways to gate:

- **Required status check** — add the `RAAST PR Review` job
  (`review` job of the `RAAST PR Review` workflow) as a required status
  check in your branch protection rules. The job fails (exit 1) when
  findings on changed lines meet the `--fail-on` threshold, which blocks
  the merge.
- **Raise the threshold** — change `--fail-on` in the workflow
  (`P0` blocks only on critical findings; `off` never blocks).

## Inputs and exit codes

| Flag | Default | Meaning |
|---|---|---|
| `--base` | (required) | Git ref to diff against, e.g. `origin/main` |
| `--path` | `.` | Path inside the repository to review |
| `--config` | auto-discover | Explicit `raast.config.json` path |
| `--fail-on` | `P1` | Threshold for exit code 1: `P0`, `P1`, `P2`, `off` |
| `--comment-out` | none | Write the markdown PR comment to this file |
| `--format` | `markdown` | Stdout report: `markdown` (comment body) or `github` (workflow annotations) |

| Exit code | Meaning |
|---|---|
| 0 | No findings at/above `--fail-on` on changed lines |
| 1 | Findings at/above the threshold on changed lines |
| 2 | Usage or engine error (not a git repo, unknown base ref, invalid config) |

The GitHub format emits one `::error` / `::warning` workflow-command per
finding (`P0`/`P1` -> error, `P2` -> warning) for inline annotations on
the Files tab.

## Limitations

- **Fork pull requests cannot post comments.** The workflow declares
  `pull-requests: write`, but GitHub restricts the `GITHUB_TOKEN` of
  `pull_request` workflows triggered from forks to read-only. For a PR
  opened from a fork the review itself still runs and inline annotations
  still appear on the Files tab (annotations are emitted by the job log,
  which does not need write access), but the "Post or update review
  comment" step fails with a 403. This is the documented, deliberate
  trade-off — see the next section for why and what to do instead.
- **Full history required.** The review computes
  `git merge-base <base> HEAD`; the workflow therefore checks out with
  `fetch-depth: 0`. Shallow clones cannot compute the merge base.
- **Static rules only.** Findings are limited to RAAST's static rules
  RTL001-RTL017 (CSS physical properties, text alignment, HTML
  direction/lang metadata, Tailwind utilities, prose typography). No
  browser or runtime behaviour is tested.
- **Comment idempotence relies on the marker.** The poster updates the
  comment whose body starts with `<!-- raast-review -->`. If someone
  deletes that comment, the next push creates a new one.
- **Scope is git-diff-driven.** The changed-file list is the merge-base
  diff filtered to supported extensions (.html .css .scss .sass .vue
  .jsx .tsx .js .ts .mjs .astro .md .mdx .txt); the config's
  include/exclude globs are not applied to this list. Files deleted by
  the PR are skipped; deleted files cannot produce findings.
- **Line numbers are working-tree line numbers** at the checked-out SHA;
  they match the PR head, not the base.
- **Engine errors are not commented.** Exit code 2 (bad ref, invalid
  config, ...) skips the comment step so a broken setup never posts a
  misleading "Passed".

## Fork pull requests: read this before changing the trigger

External contributors open PRs from forks, and for those the comment-posting
step fails (read-only token — a GitHub platform restriction, not a RAAST
bug). The tempting "fix" is switching the workflow to `pull_request_target`,
which runs with a writable token even for fork PRs.

**Do not do that.** `pull_request_target` checks out and runs workflow logic
in the context of the BASE repository with write permissions; combined with
a checkout of the PR head it lets an untrusted PR execute arbitrary code
with repository secrets — a well-known privilege-escalation vector.

Safer options, in order of preference:

1. **Accept the limitation (default).** Fork PRs still get file annotations
   and the exit-status gate; only the summary comment is missing. A
   maintainer can leave one review comment manually when merging.
2. **Label-gated rerun.** Keep `pull_request` for the report-only run, and
   add a separate `workflow_dispatch`- or `label`-triggered job that a
   maintainer explicitly starts for a specific PR. The maintainer's action
   is the trust boundary, not the event type.
3. **Post from a dedicated app or PAT** stored as a secret and used only in
   a job whose inputs a maintainer has reviewed. Never expose repository
   secrets to untrusted code paths.
