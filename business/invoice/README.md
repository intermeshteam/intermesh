# Invoicing an enterprise customer

This is billing paperwork, not part of the InterMesh product. It lives here so
it is versioned and reviewable; move it to a private repository if you would
rather it were not public. Nothing in the committed files is a secret — the
template holds placeholders, and filled invoices are gitignored.

## Why an invoice rather than a checkout

A bank's procurement department does not type a card number into a web page.
It raises a purchase order, receives an invoice, and settles it by bank
transfer on agreed terms. That path needs no payment processor at all, which
matters here: card processing is closed to a seller based in the DRC (see the
`/pricing` page and commit `2c9d3fc`).

So the constraint and the customer point the same way.

## Use

```bash
cp data/invoice.example.json data/2026-001.json   # then fill it in
python3 generate.py data/2026-001.json
```

It writes `out/2026-001.html`. Open it and print to PDF — the stylesheet is
built for A4 with print margins, so the browser's own "Save as PDF" is
enough. No LaTeX, no wkhtmltopdf, no Python packages beyond the standard
library.

Send the PDF. Do not send the HTML: an HTML file invites edits, and a PDF is
what an accounts-payable system expects to attach to a payment run.

## What you must fill in once

`data/seller.json` carries your own details and is read by every invoice, so
it is filled once rather than per invoice. It is gitignored — it holds your
bank account.

The DRC-specific identifiers an invoice from a Congolese business is expected
to carry:

| Field | What it is |
|---|---|
| `rccm` | Registre du Commerce et du Crédit Mobilier |
| `id_nat` | Identification Nationale |
| `nif` | Numéro Impôt Fiscal |

For an international transfer in USD, the payer's bank almost always needs a
**correspondent bank** as well as yours — a USD wire to Kinshasa is routed
through a bank in the United States. Ask your bank for the full set (their
SWIFT/BIC, the correspondent's SWIFT/BIC, and the account number to quote).
Leaving the correspondent out is the single most common reason a first
payment is returned weeks later.

## Tax — read this before sending the first one

**I am not able to tell you the correct VAT treatment, and you should not take
the default in this template as advice.** DRC VAT (TVA) is 16%, but services
exported to a customer established abroad are commonly treated differently,
and the answer depends on facts about your business that a template cannot
know.

Set `vat_rate` to what your accountant tells you. The template will print
whatever you set, including `0`, and prints the note in `vat_note` next to
it — use that line to state the legal basis your accountant gives you. An
invoice with the wrong VAT treatment is a problem you discover at an audit,
long after the money is spent.

The same goes for whether your customer must apply a withholding tax in their
own country. Large companies often do, and it arrives as a payment smaller
than the invoice. Agree that in writing before signing, not after.

## Numbering

Invoice numbers must be sequential and gapless — that is what makes a set of
books auditable. `generate.py` refuses to overwrite an existing output file so
a number cannot silently be reused. If you cancel an invoice, issue a credit
note rather than deleting it.
