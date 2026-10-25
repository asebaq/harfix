"""`harfix scan` and `harfix decode` for PDFs, `harfix check` and `harfix repair` for
extracted text."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .decode import MIN_KNOWN, HarfixError, decode_pdf
from .detect import ROUTES, assess_document
from .pdf import scan_pdf
from .repair import repair_text


def _parse_pages(spec: str) -> list[int]:
    pages: set[int] = set()
    for part in spec.split(","):
        start, _, end = part.strip().partition("-")
        try:
            first = int(start)
            last = int(end) if end else first
        except ValueError:
            first = last = 0
        if first < 1 or last < first:
            raise argparse.ArgumentTypeError(
                f"invalid page range {part.strip()!r} (expected e.g. 1-5,9)"
            )
        pages.update(range(first, last + 1))
    return sorted(pages)


def _compact(numbers: list[int]) -> str:
    """`[3, 4, 5, 9]` as `3-5,9`."""
    runs: list[list[int]] = []
    for n in sorted(numbers):
        if runs and n == runs[-1][1] + 1:
            runs[-1][1] = n
        else:
            runs.append([n, n])
    return ",".join(str(a) if a == b else f"{a}-{b}" for a, b in runs)


def _found_pages(path: str, requested: list[int] | None, found: list[int]) -> None:
    """Fail when none of the requested pages exist; warn about the missing ones."""
    if requested is None:
        return
    missing = sorted(set(requested) - set(found))
    if not found:
        raise HarfixError(f"{path} has no page {_compact(missing)}")
    if missing:
        print(f"harfix: {path} has no page {_compact(missing)}", file=sys.stderr)


def _read_text(file: str) -> str:
    data = sys.stdin.buffer.read() if file == "-" else Path(file).read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        name = "stdin" if file == "-" else file
        raise HarfixError(f"{name} is not UTF-8 text (byte {error.start})") from error


def _fails(route: str, fail_on: str | None) -> bool:
    return fail_on is not None and ROUTES.index(route) >= ROUTES.index(fail_on)


# Printed when no segment or page had enough Arabic text to judge: not the same as `keep`,
# and a failure under `--fail-on`, since nothing was checked.
NOTHING_JUDGED = "no Arabic text to judge"


def _scan(args: argparse.Namespace) -> int:
    worst = "keep"
    reports, judged = [], True
    for path in args.pdf:
        report = scan_pdf(path, pages=args.pages)
        _found_pages(path, args.pages, [p.page for p in report.pages])
        reports.append(report)
        for page in report.pages:
            worst = max(worst, page.route, key=ROUTES.index)
        judged &= any(
            page.route != "keep" or any(f.assessment.decisive for f in page.fonts)
            for page in report.pages
        )
    if args.json:
        payload = [r.to_dict() for r in reports]
        json.dump(
            payload[0] if len(payload) == 1 else payload, sys.stdout, ensure_ascii=False, indent=2
        )
        print()
    else:
        for report in reports:
            print(f"{report.path}")
            counts = ", ".join(f"{route}={n}" for route, n in report.route_counts.items() if n)
            print(f"  pages: {counts}")
            if not any(
                page.route != "keep" or any(f.assessment.decisive for f in page.fonts)
                for page in report.pages
            ):
                print(f"  {NOTHING_JUDGED}")
            decodable = [p.page for p in report.pages if p.decodable]
            if decodable:
                print(
                    f"  {len(decodable)} ocr page(s) use fonts `harfix decode` can read: "
                    f"harfix decode {report.path}"
                )
            for page in report.pages:
                if page.route == "keep" and not args.verbose:
                    continue
                reasons = ", ".join(page.reasons) or "-"
                hint = " (decodable)" if page.decodable else ""
                print(f"  p{page.page:<5} {page.route:<9} {reasons}{hint}")
                if args.verbose:
                    for font in page.fonts:
                        a = font.assessment
                        bits = a.metrics.get("bits", "-")
                        print(
                            f"         {font.font[:40]:<40} {a.route:<9} "
                            f"letters={a.metrics.get('arabic_letters')} bits={bits} "
                            f"{','.join(a.reasons)}"
                        )
    return 1 if _fails(worst, args.fail_on) or (args.fail_on and not judged) else 0


def _check(args: argparse.Namespace) -> int:
    report = assess_document(_read_text(args.file))
    judged = any(s.assessment.decisive for s in report.segments)
    if args.json:
        json.dump(report.to_dict(), sys.stdout, ensure_ascii=False, indent=2)
        print()
    elif not judged:
        print(NOTHING_JUDGED)
    else:
        print(f"{report.route}: {', '.join(report.reasons) or 'no issues found'}")
        counts = {route: 0 for route in ROUTES}
        for segment in report.segments:
            counts[segment.assessment.route] += 1
        unit = "pages" if any(s.page is not None for s in report.segments) else "segments"
        print(f"  {unit}: " + ", ".join(f"{route}={n}" for route, n in counts.items() if n))
        for segment in report.segments:
            a = segment.assessment
            if a.route == "keep" and not args.verbose:
                continue
            where = (
                f"p{segment.page}"
                if segment.page is not None
                else f"lines {segment.start_line}-{segment.end_line}"
            )
            print(f"  {where:<16} {a.route:<9} {', '.join(a.reasons) or '-'}")
            if args.verbose:
                for key, value in a.metrics.items():
                    print(f"      {key}: {value}")
    return 1 if _fails(report.route, args.fail_on) or (args.fail_on and not judged) else 0


def _where(page: int | None, start: int, end: int) -> str:
    return f"p{page}" if page is not None else f"lines {start}-{end}"


def _repair(args: argparse.Namespace) -> int:
    result = repair_text(_read_text(args.file))
    if args.json:
        json.dump(result.to_dict(), sys.stdout, ensure_ascii=False, indent=2)
        print()
    elif args.output:
        Path(args.output).write_text(result.text, encoding="utf-8")
    else:
        sys.stdout.write(result.text)
    if not args.json:
        for c in result.changes:
            unit = "lines" if c.reason == "visual_order" else "characters"
            where = _where(c.page, c.start_line, c.end_line)
            print(f"repaired {where}: {c.reason} ({c.count} {unit})", file=sys.stderr)
        for s in result.unrepaired:
            where = _where(s.page, s.start_line, s.end_line)
            reasons = ", ".join(s.assessment.reasons)
            print(f"not repaired {where}: {s.assessment.route} ({reasons})", file=sys.stderr)
    worst = max((s.assessment.route for s in result.unrepaired), default="keep", key=ROUTES.index)
    return 1 if _fails(worst, args.fail_on) else 0


def _decode(args: argparse.Namespace) -> int:
    pages = decode_pdf(args.pdf, pages=args.pages)
    _found_pages(args.pdf, args.pages, [p.page for p in pages])
    # Pages with glyphs to decode that were left out: too few glyphs readable, or text that
    # fails the check. Pages with nothing to decode are not counted.
    left_out = [p.page for p in pages if not p.trusted and (p.assessment or _unreadable(p))]
    if args.json:
        json.dump([p.to_dict() for p in pages], sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 1 if args.fail_on_untrusted and left_out else 0
    # Only trusted pages carry text; the others stay empty so page positions are kept.
    text = "\f".join(p.text if p.trusted else "" for p in pages)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    for p in pages:
        if p.assessment is None:
            why = (
                f"only {p.known_share:.0%} of its glyphs can be read"
                if _unreadable(p)
                else "no glyphs in fonts harfix can decode"
            )
            print(f"not decoded p{p.page}: {why}", file=sys.stderr)
        elif p.trusted:
            print(f"decoded p{p.page}", file=sys.stderr)
        else:
            reasons = ", ".join(p.assessment.reasons)
            print(
                f"not trusted p{p.page}: decoded text routes to {p.assessment.route} ({reasons})",
                file=sys.stderr,
            )
    return 1 if args.fail_on_untrusted and left_out else 0


def _unreadable(page) -> bool:
    return bool(page.decoded_share) and page.known_share < MIN_KNOWN


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harfix", description="Quality gate for Arabic text extracted from PDFs."
    )
    parser.add_argument("--version", action="version", version=f"harfix {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="audit the text layer of PDFs, per page and per font")
    scan.add_argument("pdf", nargs="+", help="PDF files")
    scan.add_argument("--pages", type=_parse_pages, help="1-based pages, e.g. 1-5,9")
    scan.add_argument("--json", action="store_true", help="print the full report as JSON")
    scan.add_argument("-v", "--verbose", action="store_true", help="show every page and font")
    scan.add_argument(
        "--fail-on",
        choices=ROUTES[1:],
        help="exit 1 if any page needs this route or worse, or if no page had Arabic text to judge",
    )
    scan.set_defaults(func=_scan)

    check = sub.add_parser(
        "check", help="assess text produced by any extractor, page by page (form feeds)"
    )
    check.add_argument("file", nargs="?", default="-", help="UTF-8 text file, or - for stdin")
    check.add_argument("--json", action="store_true", help="print the full report as JSON")
    check.add_argument(
        "-v", "--verbose", action="store_true", help="show every segment and its metrics"
    )
    check.add_argument(
        "--fail-on",
        choices=ROUTES[1:],
        help="exit 1 if any segment needs this route or worse, or if there is no Arabic "
        "text to judge",
    )
    check.set_defaults(func=_check)

    repair = sub.add_parser(
        "repair", help="apply the safe fixes for text that `check` routes to repair"
    )
    repair.add_argument("file", nargs="?", default="-", help="UTF-8 text file, or - for stdin")
    repair.add_argument("-o", "--output", help="write the repaired text here instead of stdout")
    repair.add_argument(
        "--json", action="store_true", help="print text, changes and unrepaired segments"
    )
    repair.add_argument(
        "--fail-on",
        choices=ROUTES[2:],
        help="exit 1 if any segment left unrepaired needs this route or worse",
    )
    repair.set_defaults(func=_repair)

    decode = sub.add_parser(
        "decode", help="decode pre-Unicode Arabic fonts in a PDF with the packaged font maps"
    )
    decode.add_argument("pdf", help="PDF file")
    decode.add_argument("--pages", type=_parse_pages, help="1-based pages, e.g. 1-5,9")
    decode.add_argument("-o", "--output", help="write the decoded text here instead of stdout")
    decode.add_argument("--json", action="store_true", help="print every page with its check")
    decode.add_argument(
        "--fail-on-untrusted",
        action="store_true",
        help="exit 1 if a page with glyphs to decode is left out (too few glyphs readable, "
        "or the decoded text fails the check)",
    )
    decode.set_defaults(func=_decode)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except HarfixError as error:
        print(f"harfix: {error}", file=sys.stderr)
    except BrokenPipeError:
        raise
    except OSError as error:
        where = f"{error.filename}: " if error.filename else ""
        print(f"harfix: {where}{error.strerror or error}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
