# Auto-Fix 2.0

`raast fix` rewrites files, but only within a strict classification of what a
program may change on its own. This document describes the three-tier fix
model introduced in Auto-Fix 2.0, the safety policy around it, and — just as
important — what auto-fix will not do.

Default mode is dry-run: nothing is written until `--apply` is passed. Every
applied change leaves a backup and a journal entry behind, and `raast revert`
can undo a whole fix run.

## The three-tier model

Every rule id maps to exactly one tier (`raast.fixer.FIX_TIERS`, query with
`raast.fixer.tier_for(rule)`; unknown ids fall back to `manual`):

| Tier | Rules | Why this tier |
|---|---|---|
| **safe** | RTL001, RTL002, RTL004, RTL005, RTL008, RTL011 | Mechanical, reversible rewrites: `margin-left/right` → `margin-inline-start/end`, `padding-left/right` → `padding-inline-start/end`, `text-align: left/right` → `start/end`, removal of `letter-spacing` on Arabic script, Tailwind `ml-/mr-/pl-/pr-/text-left/text-right` → logical utilities, and Persian ZWNJ compound joins (with `--zwnj`). The transformation is unambiguous and the old content is always recoverable. |
| **suggested** | RTL009, RTL010 | Correct for the profile but opinionated, so they are opt-in twice: only under `--tier all` AND behind their existing flags — `--zwnj-punct` (Latin `, ; ?` → Arabic `، ؛ ؟`) and `--zwnj-digits` (Western digits → Persian digits, fa only). Digits inside LTR atoms (URLs, emails, phones, prices with currency symbols) and inside HTML tags/attributes are never converted. |
| **manual** | RTL003, RTL006, RTL007, RTL012, RTL013, RTL014, RTL015, RTL016, RTL017 | Never auto-applied. These need human judgment — see "What auto-fix will not do" below. The engine reports them as findings; the fixer leaves them alone. |

The CLI selects a tier policy with `--tier`:

- `--tier safe` (default) — apply only safe-tier fixes.
- `--tier all` — safe-tier fixes plus suggested-tier transforms, which stay
  gated by `--zwnj` / `--zwnj-digits` / `--zwnj-punct`.
- There is no `--tier manual`; manual-tier findings are never applicable.

After a run with fixes, the CLI prints a breakdown:

```
tier breakdown: safe=4 suggested=1 manual(review-only)=0
```

and, when findings remain that the tier policy did not address:

```
2 finding(s) not auto-applied (manual review or opt-in gates) — use 'raast fix --tier all --zwnj ...' to include suggested fixes
```

## Safety policy

1. **Dry-run by default.** `raast fix <path>` computes and shows the unified
   diff without writing. Add `--apply` to write; add `--diff` to still see
   diffs while applying.
2. **Backups before every write.** `--apply` copies each file into
   `.raast-backup/<relative-path>` (via `shutil.copy2`, metadata preserved)
   before overwriting it.
3. **Append-only journal.** Each applied fix appends an entry to
   `.raast-backup/journal.json`:
   ```json
   {
     "timestamp": "2026-01-01T12:00:00+00:00",
     "file": "src/page.html",
     "backup": "src/page.html",
     "rules": ["RTL001", "RTL004"],
     "fix_count": 2
   }
   ```
   `backup` is the copy's path relative to the backup directory; `file` is the
   repo-relative path that was overwritten. The journal is the single source
   of truth for the backup-to-file mapping.
4. **Revert is journal-driven.** `raast revert [path]` restores exactly the
   files recorded in the journal, byte-identical, removes the restored backups
   and clears the journal. Without a usable journal it refuses to guess: if
   `.raast-backup/` still holds copies but no journal covers them, revert
   prints an honest explanation and exits 1 rather than restoring blind.
5. **Nothing outside the root.** Revert touches only paths inside the target
   root and reads/deletes only inside `root/.raast-backup/`. Journal entries
   with absolute paths or `..` components are refused.

## CLI examples

Dry-run diff (default tier, writes nothing):

```
$ raast fix src/ --diff
--- src/page.html (before)
+++ src/page.html (after)
@@ ...
-.panel { margin-left: 24px; text-align: left; }
+.panel { margin-inline-start: 24px; text-align: start; }

DRY RUN — 2 fix(es) across 1 file(s)
tier breakdown: safe=2 suggested=0 manual(review-only)=1
1 finding(s) not auto-applied (manual review or opt-in gates) — use 'raast fix --tier all --zwnj ...' to include suggested fixes
re-run with --apply to write changes (backups land in .raast-backup/)
```

Apply safe fixes plus suggested-tier transforms (digit conversion still needs
its flag):

```
$ raast fix src/ --tier all --zwnj-digits --apply
```

Undo a whole fix run (non-interactive sessions need `--yes`; without it the
command prints the plan and, on a terminal, asks for confirmation):

```
$ raast revert src/
revert plan — 1 journal entr(y/ies) under src/.raast-backup:
  restore src/page.html  <-  src/page.html
re-run with --yes to apply

$ raast revert src/ --yes
restored src/page.html
1 file(s) restored; journal cleared
```

## What auto-fix will not do

The manual tier exists because these decisions cannot be made reliably by a
program:

- **Positioning semantics (RTL003).** A physical `left:`/`right:` may anchor a
  badge, a tooltip, a canvas overlay, or a JS-measured position. Some of those
  are intentional; converting them to `inset-inline-*` changes behavior in
  ways only a human can judge.
- **Document-level attributes (RTL006, RTL014).** `dir` and `lang` on
  `<html>` are owned by templates and i18n pipelines. Writing them blindly
  could fight a server-side direction switch or a multi-locale build.
- **Motion and transform intent (RTL007).** `translate-x-*` drives drawers,
  sliders and shimmer effects. Whether it should mirror depends on what the
  animation means; mirroring it blindly can break a deliberately symmetric
  effect.
- **Bidi markup choices (RTL012, RTL015, RTL016).** Isolating an atom with
  `<bdi>`, `<span dir="ltr">` or `dir="auto"` changes the DOM. The right
  wrapper depends on the content model and styling, so the engine reports the
  run and leaves the markup decision to the author.
- **Forced direction on RTL content (RTL013).** `dir="ltr"` on an
  Arabic-only element looks wrong, but it may be a deliberate override for
  mixed embeds; removing it automatically could break a controlled layout.
- **i18n copy decisions (RTL017).** Adding `¿`/`¡` is a copy edit; a program
  that rewrites editorial prose is a program that rewrites meaning.
- **Suggested-tier rewrites by default (RTL009, RTL010).** Converting
  punctuation or digits is correct per the language profile but still an
  editorial choice — phones, serials and prices can legitimately keep Western
  forms. They stay behind `--tier all` and their opt-in flags.

In every case the finding remains in `raast doctor` output with its
explanation and suggested fix, so a human can decide.
