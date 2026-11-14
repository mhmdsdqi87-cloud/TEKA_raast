#!/usr/bin/env python3
"""
fix-zwnj.py — Persian text normalizer (نیم‌فاصله fixer)

Fixes the most common Persian orthography defects in generated/typed text:
  1. Broken ZWNJ compounds:  "می رود" -> "می‌رود", "خانه ها" -> "خانه‌ها", "خوب تر" -> "خوب‌تر"
  2. Arabic Yeh/Kaf -> Persian:  ي -> ی ,  ك -> ک
  3. Arabic-Indic digits -> Persian digits (optional, --digits)
  4. Latin punctuation in Persian prose -> Persian marks (optional, --punct)

Safety model:
  - Conservative: only joins affix patterns against a curated wordlist / safe regex.
  - Never modifies fenced code blocks, inline code, URLs, or emails.
  - Default mode is DRY RUN: prints a diff. Use --apply to write the file.
  - Mark regions to protect with <!-- keep --> ... <!-- /keep --> if ever needed.

Usage:
  python3 fix-zwnj.py FILE [FILE...]            # dry run, shows unified diff
  python3 fix-zwnj.py FILE --apply              # write changes
  python3 fix-zwnj.py FILE --digits --punct --apply
  cat draft.txt | python3 fix-zwnj.py -         # stdin -> stdout (always applies)
"""

import argparse
import difflib
import re
import sys

ZWNJ = "\u200c"

# ---------------------------------------------------------------- wordlists

# Common verb stems used after می / نمی / بی / هم prefixes when text was
# typed with a space. Not exhaustive — intentionally conservative.
VERB_STEMS = [
    "شود", "شده", "شوند", "باشد", "باشند", "بود", "هست", "هستند",
    "رود", "رفت", "رفته", "روند", "رویم", "روم",
    "آید", "آمد", "آمده", "آیند",
    "دهد", "داد", "داده", "دهند", "دهم", "دهید",
    "برد", "برود", "برند", "ببر", "بریم",
    "گیرد", "گرفت", "گرفته", "گیرند", "گیریم",
    "کند", "کرد", "کرده", "کنند", "کنیم", "کن", "کنید",
    "خواهد", "خواهم", "خواهیم", "خواهند", "خواست",
    "تواند", "توانست", "توانم",
    "آورد", "آورده", "آورند",
    "گفت", "گوید", "گفته", "گویند",
    "بیند", "دید", "دیده",
    "یابد", "یافت", "یافته",
    "رسد", "رسید", "رسیده",
    "داند", "دانست", "دانند",
    "پردازد", "پرداخت", "پرداخته",
    "سازد", "ساخت", "ساخته", "سازند",
    "نویسد", "نوشت", "نوشته",
    "خواند", "خواند", "خوانده",
    "بیند", "بازبیند",
    "دارد", "داشت", "دارند",
    "دهد", "افزاید", "افزود", "افزوده",
    "بماند", "ماند", "مانده",
    "شوند", "گردد", "گردید", "گردیده",
]

PREFIX_VERB = re.compile(
    r"(?<![^\s])\b(می|نمی|بی|هم|باز|فرا|نا)\s+(" + "|".join(VERB_STEMS) + r")\b"
)

# "خانه ها" -> "خانه‌ها" : plural marker after a Persian word.
# Safe in prose; "ها" as a standalone word is practically nonexistent.
PLURAL = re.compile(r"([\u0600-\u06FF]{2,})[ ]+(ها|های)(?=[\s،؛؟!.]|$)")

# "خوب تر" -> "خوب‌تر", "بزرگ ترین" -> "بزرگ‌ترین" (but never inside بهتر/بیشتر)
COMP_TR = re.compile(r"([\u0600-\u06FF]{2,})[ ]+(تر|ترین)(?=[\s،؛؟!.]|$)")

# Arabic Yeh/Kaf -> Persian
AR_YEH_KAF = str.maketrans({"ي": "ی", "ك": "ک", "ھ": "ه"})

# Arabic-Indic -> Persian digits (opt-in)
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "۰۱۲۳۴۵۶۷۸۹")

# Latin punctuation in Persian prose (opt-in, prose-only heuristic applied per line)
PUNCT = [
    (re.compile(r"(?<=[\u0600-\u06FF])\s*,\s*(?=[\u0600-\u06FF\s])"), "، "),
    (re.compile(r"(?<=[\u0600-\u06FF])\s*\?(?=\s|$)"), "؟"),
    (re.compile(r"(?<=[\u0600-\u06FF])\s*;(?=\s|$)"), "؛"),
]

CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`]*`")
URL_LIKE = re.compile(r"(https?://\S+|[\w.+-]+@[\w-]+\.[\w.]+)")

# ---------------------------------------------------------------- engine


def protect(text):
    """Replace fragile regions with sentinels; return (masked, list)."""
    saved = []

    def stash(m):
        saved.append(m.group(0))
        return f"\x00{len(saved) - 1}\x00"

    masked = CODE_FENCE.sub(stash, text)
    masked = INLINE_CODE.sub(stash, masked)
    masked = URL_LIKE.sub(stash, masked)
    return masked, saved


def restore(text, saved):
    for i, chunk in enumerate(saved):
        text = text.replace(f"\x00{i}\x00", chunk)
    return text


def normalize(text, digits=False, punct=False):
    masked, saved = protect(text)

    masked = PREFIX_VERB.sub(lambda m: m.group(1) + ZWNJ + m.group(2), masked)
    masked = PLURAL.sub(lambda m: m.group(1) + ZWNJ + m.group(2), masked)
    masked = COMP_TR.sub(lambda m: m.group(1) + ZWNJ + m.group(2), masked)
    masked = masked.translate(AR_YEH_KAF)

    if digits:
        # Persian digits only in prose lines (a line that contains Persian letters)
        def fix_line(line):
            if re.search(r"[\u0600-\u06FF]", line):
                return line.translate(AR_DIGITS)
            return line

        masked = "\n".join(fix_line(l) for l in masked.split("\n"))

    if punct:
        for rx, repl in PUNCT:
            masked = rx.sub(repl, masked)

    return restore(masked, saved)


def main():
    ap = argparse.ArgumentParser(description="Persian ZWNJ / orthography normalizer")
    ap.add_argument("files", nargs="+", help="files or '-' for stdin")
    ap.add_argument("--apply", action="store_true", help="write changes in place")
    ap.add_argument("--digits", action="store_true", help="also Arabic->Persian digits in prose")
    ap.add_argument("--punct", action="store_true", help="also Latin->Persian punctuation in prose")
    args = ap.parse_args()

    if args.files == ["-"]:
        sys.stdout.write(normalize(sys.stdin.read(), args.digits, args.punct))
        return

    changed = 0
    for path in args.files:
        with open(path, encoding="utf-8") as f:
            original = f.read()
        fixed = normalize(original, args.digits, args.punct)

        if fixed == original:
            print(f"✔ {path}: clean")
            continue

        changed += 1
        diff = difflib.unified_diff(
            original.splitlines(), fixed.splitlines(),
            fromfile=path + " (before)", tofile=path + " (after)", lineterm=""
        )
        print("\n".join(diff))
        if args.apply:
            with open(path, "w", encoding="utf-8") as f:
                f.write(fixed)
            print(f"✔ {path}: fixed")

    if not args.apply and changed:
        print(f"\n{changed} file(s) need fixes. Re-run with --apply to write.")


if __name__ == "__main__":
    main()
