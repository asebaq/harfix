"""`harfix scan` for PDFs and `harfix check` for text produced by any extractor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .detect import ROUTES, assess_document
from .pdf import HarfixError, scan_pdf


def _parse_pages(spec: str) -> list[int]:
    pages: set[int] = set()
    for part in spec.split(","):
        start, _, end = part.strip().partition("-")
        first = int(start)
        last = int(end) if end else first
        if first < 1 or last < first:
            raise argparse.ArgumentTypeError(f"invalid page range: {part!r}")
        pages.update(range(first, last + 1))
    return sorted(pages)


def _fails(route: str, fail_on: str | None) -> bool:
    return fail_on is not None and ROUTES.index(route) >= ROUTES.index(fail_on)


def _scan(args: argparse.Namespace) -> int:
    worst = "keep"
    reports = []
    for path in args.pdf:
        try:
            report = scan_pdf(path, pages=args.pages)
        except (HarfixError, FileNotFoundError) as error:
            print(f"harfix: {error}", file=sys.stderr)
            return 2
        reports.append(report)
        for page in report.pages:
            worst = max(worst, page.route, key=ROUTES.index)

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
            for page in report.pages:
                if page.route == "keep" and not args.verbose:
                    continue
                reasons = ", ".join(page.reasons) or "-"
                print(f"  p{page.page:<5} {page.route:<9} {reasons}")
                if args.verbose:
                    for font in page.fonts:
                        a = font.assessment
                        bits = a.metrics.get("bits", "-")
                        print(
                            f"         {font.font[:40]:<40} {a.route:<9} "
                            f"letters={a.metrics.get('arabic_letters')} bits={bits} "
                            f"{','.join(a.reasons)}"
                        )
    return 1 if _fails(worst, args.fail_on) else 0


def _check(args: argparse.Namespace) -> int:
    text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    report = assess_document(text)
    if args.json:
        json.dump(report.to_dict(), sys.stdout, ensure_ascii=False, indent=2)
        print()
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
    return 1 if _fails(report.route, args.fail_on) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harfix", description="Quality gate for Arabic text extracted from PDFs."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="audit the text layer of PDFs, per page and per font")
    scan.add_argument("pdf", nargs="+")
    scan.add_argument("--pages", type=_parse_pages, help="1-based pages, e.g. 1-5,9")
    scan.add_argument("--json", action="store_true", help="print the full report as JSON")
    scan.add_argument("-v", "--verbose", action="store_true", help="show every page and font")
    scan.add_argument(
        "--fail-on", choices=ROUTES[1:], help="exit 1 if any page needs this route or worse"
    )
    scan.set_defaults(func=_scan)

    check = sub.add_parser(
        "check", help="assess text produced by any extractor, page by page (form feeds)"
    )
    check.add_argument("file", nargs="?", default="-", help="UTF-8 text file, or - for stdin")
    check.add_argument("--json", action="store_true")
    check.add_argument(
        "-v", "--verbose", action="store_true", help="show every segment and its metrics"
    )
    check.add_argument(
        "--fail-on", choices=ROUTES[1:], help="exit 1 if any segment needs this route or worse"
    )
    check.set_defaults(func=_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
