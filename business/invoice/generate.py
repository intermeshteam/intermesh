#!/usr/bin/env python3
"""Fills template.html from a JSON file and writes an invoice ready to print.

    python3 generate.py data/2026-001.json

Standard library only. The browser is the PDF renderer, so there is no
toolchain to install and nothing that drifts out of step with the template.

Two decisions worth knowing about:

  * Money is handled in integer cents, never in floats. `0.1 + 0.2` is not
    `0.3` in binary floating point, and an invoice that is off by a cent is
    an invoice a payables system will query.
  * An existing output file is never overwritten. Invoice numbers have to be
    sequential and gapless for a set of books to be auditable, so silently
    reusing one is the failure worth preventing.
"""

from __future__ import annotations

import html
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template.html"
OUT_DIR = HERE / "out"


class InvoiceError(Exception):
    """Something in the data file is wrong. Reported without a traceback."""


# ---------------------------------------------------------------- money


def to_cents(value: object, field: str) -> int:
    """Accepts 1200, 1200.50 or "1200.50" and returns integer cents.

    Strings go through Decimal-free parsing on purpose: the input is a
    human-written JSON file, and quietly accepting "1 200,50" would be worse
    than refusing it.
    """
    if isinstance(value, bool):
        raise InvoiceError(f"{field}: expected an amount, got a boolean")
    if isinstance(value, int):
        return value * 100
    if isinstance(value, float):
        # round() rather than int(): int(19.99 * 100) is 1998.
        return round(value * 100)
    if isinstance(value, str):
        text = value.strip().replace(" ", "")
        if not re.fullmatch(r"-?\d+(\.\d{1,2})?", text):
            raise InvoiceError(f"{field}: {value!r} is not an amount like 1200 or 1200.50")
        neg = text.startswith("-")
        whole, _, frac = text.lstrip("-").partition(".")
        cents = int(whole) * 100 + int((frac or "0").ljust(2, "0"))
        return -cents if neg else cents
    raise InvoiceError(f"{field}: expected an amount, got {type(value).__name__}")


def money(cents: int, currency: str) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    whole, rest = divmod(cents, 100)
    return f"{sign}{currency} {whole:,}.{rest:02d}".replace(",", " ")


# ---------------------------------------------------------------- helpers


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def lines_html(value: object) -> str:
    """A string or list of strings becomes <br>-separated escaped lines."""
    if value is None:
        return ""
    items = value if isinstance(value, list) else str(value).splitlines()
    return "<br>".join(esc(line) for line in items if str(line).strip())


def ids_html(source: dict, keys: list[tuple[str, str]]) -> str:
    parts = [f"{esc(label)} {esc(source[key])}" for key, label in keys if source.get(key)]
    return " &middot; ".join(parts)


def require(source: dict, key: str, where: str) -> object:
    if key not in source or source[key] in (None, "", []):
        raise InvoiceError(f"{where}: missing required field {key!r}")
    return source[key]


def add_days(iso: str, days: int) -> str:
    try:
        return (date.fromisoformat(iso) + timedelta(days=days)).isoformat()
    except ValueError as exc:
        raise InvoiceError(f"issue_date: {iso!r} is not a date like 2026-09-02") from exc


# ---------------------------------------------------------------- build


def build(data: dict, seller: dict) -> tuple[str, str]:
    currency = str(data.get("currency", "USD")).upper()

    number = str(require(data, "invoice_number", "invoice"))
    if "/" in number or "\\" in number:
        raise InvoiceError(f"invoice_number: {number!r} may not contain a path separator")

    issue_date = str(require(data, "issue_date", "invoice"))
    net_days = int(data.get("net_days", 30))
    due_date = str(data.get("due_date") or add_days(issue_date, net_days))

    # --- line items -----------------------------------------------------
    raw_items = require(data, "items", "invoice")
    if not isinstance(raw_items, list) or not raw_items:
        raise InvoiceError("items: expected a non-empty list")

    rows, subtotal = [], 0
    for index, item in enumerate(raw_items, start=1):
        # "item 1", not "items[0]": the reader is editing JSON by hand and
        # a zero-based index in an error message invites an off-by-one edit.
        where = f"item {index}"
        title = str(require(item, "title", where))
        qty = item.get("quantity", 1)
        if not isinstance(qty, (int, float)) or isinstance(qty, bool) or qty <= 0:
            raise InvoiceError(f"{where}: quantity must be a positive number")
        unit = to_cents(require(item, "unit_price", where), f"{where}.unit_price")

        amount = round(unit * qty)
        subtotal += amount

        qty_text = str(int(qty)) if float(qty).is_integer() else f"{qty:g}"
        desc = item.get("description")
        rows.append(
            "<tr>"
            f'<td><strong>{esc(title)}</strong>'
            + (f'<div class="item-desc">{lines_html(desc)}</div>' if desc else "")
            + "</td>"
            f'<td class="num">{esc(qty_text)}</td>'
            f'<td class="num">{money(unit, currency)}</td>'
            f'<td class="num">{money(amount, currency)}</td>'
            "</tr>"
        )

    # --- VAT ------------------------------------------------------------
    # No default rate. The correct treatment for a service exported from the
    # DRC depends on facts a template cannot know, so it has to be stated in
    # the data file rather than assumed here. See README.md.
    if "vat_rate" not in data:
        raise InvoiceError(
            "vat_rate: required — set it to what your accountant tells you "
            "(0 is a valid answer, and prints as an explicit line)"
        )
    vat_rate = data["vat_rate"]
    if not isinstance(vat_rate, (int, float)) or isinstance(vat_rate, bool) or vat_rate < 0:
        raise InvoiceError("vat_rate: expected a percentage such as 0 or 16")

    vat = round(subtotal * vat_rate / 100)
    total = subtotal + vat

    vat_row = (
        f'<tr><td class="muted">VAT ({vat_rate:g}%)</td>'
        f"<td>{money(vat, currency)}</td></tr>"
    )
    vat_note = data.get("vat_note", "")
    vat_note_html = f'<p class="vat-note">{lines_html(vat_note)}</p>' if vat_note else ""

    # --- bank -----------------------------------------------------------
    bank = require(seller, "bank", "seller")
    bank_rows = []
    for label, key in [
        ("Account name", "account_name"),
        ("Bank", "bank_name"),
        ("Account number", "account_number"),
        ("IBAN", "iban"),
        ("SWIFT / BIC", "swift"),
        ("Correspondent bank", "correspondent_bank"),
        ("Correspondent SWIFT", "correspondent_swift"),
        ("Bank address", "bank_address"),
    ]:
        if bank.get(key):
            bank_rows.append(f"<dt>{esc(label)}</dt><dd>{lines_html(bank[key])}</dd>")
    if not bank_rows:
        raise InvoiceError("seller.bank: no details filled in — the customer cannot pay")

    po = data.get("po_number")
    po_line = f'<div><span class="muted">PO</span> <strong>{esc(po)}</strong></div>' if po else ""

    notes = data.get("notes")
    notes_html = f"<p>{lines_html(notes)}</p>" if notes else ""

    filled = {
        "doc_title": esc(data.get("doc_title", "Invoice")),
        "invoice_number": esc(number),
        "issue_date": esc(issue_date),
        "due_date": esc(due_date),
        "po_line": po_line,
        "seller_company": esc(require(seller, "company", "seller")),
        "seller_address_html": lines_html(seller.get("address")),
        "seller_ids_html": ids_html(
            seller, [("rccm", "RCCM"), ("id_nat", "ID. NAT."), ("nif", "NIF"),
                     ("email", "&#9993;"), ("phone", "&#9742;")]
        ),
        "buyer_company": esc(require(data, "buyer_company", "invoice")),
        "buyer_address_html": lines_html(data.get("buyer_address")),
        "buyer_ids_html": ids_html(data, [("buyer_vat_id", "VAT ID"), ("buyer_reg_id", "Reg.")]),
        "buyer_contact": esc(data.get("buyer_contact", "")),
        "buyer_email": esc(data.get("buyer_email", "")),
        "items_html": "\n      ".join(rows),
        "subtotal": money(subtotal, currency),
        "vat_row": vat_row,
        "total": money(total, currency),
        "vat_note_html": vat_note_html,
        "bank_html": "\n      ".join(bank_rows),
        "payment_terms": esc(
            data.get("payment_terms", f"Payable within {net_days} days of the issue date.")
        ),
        "notes_html": notes_html,
        "footer_text": lines_html(
            seller.get("footer", f"{seller.get('company', '')} — thank you for your business.")
        ),
    }

    template = TEMPLATE.read_text(encoding="utf-8")
    for key, value in filled.items():
        template = template.replace("{{" + key + "}}", value)

    leftover = re.findall(r"\{\{(\w+)\}\}", template)
    if leftover:
        raise InvoiceError(f"template placeholders left unfilled: {', '.join(sorted(set(leftover)))}")

    return number, template


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        print("\nusage: python3 generate.py data/<invoice>.json", file=sys.stderr)
        return 2

    data_path = Path(argv[1])
    seller_path = HERE / "data" / "seller.json"

    try:
        if not data_path.exists():
            raise InvoiceError(f"{data_path} does not exist")
        if not seller_path.exists():
            raise InvoiceError(
                f"{seller_path} does not exist — copy data/seller.example.json to it and fill it in"
            )

        data = json.loads(data_path.read_text(encoding="utf-8"))
        seller = json.loads(seller_path.read_text(encoding="utf-8"))
        number, document = build(data, seller)

        OUT_DIR.mkdir(exist_ok=True)
        out_path = OUT_DIR / f"{number}.html"
        if out_path.exists():
            raise InvoiceError(
                f"{out_path} already exists. Invoice numbers must not be reused — "
                "issue a credit note rather than reissuing this one."
            )
        out_path.write_text(document, encoding="utf-8")

    except InvoiceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON — {exc}", file=sys.stderr)
        return 1

    print(f"wrote {out_path}")
    print("open it and print to PDF (A4), then send the PDF rather than the HTML")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
