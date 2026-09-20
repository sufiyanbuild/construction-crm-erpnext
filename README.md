# Construction CRM for ERPNext

A CRM and project-lifecycle application for construction and contracting
businesses, built on [Frappe](https://frappeframework.com) and
[ERPNext](https://erpnext.com) v16.

It covers the whole commercial thread a contractor actually works through —
from an incoming enquiry or tender, through estimation, quotation, award,
project execution and procurement, to progress billing, retention, warranty and
project closure — with every stage linked back to the one before it.

The app extends standard ERPNext rather than replacing it. Where ERPNext already
solves a problem (projects, tasks, invoicing, payments, attachments, email),
that functionality is configured and used as-is; custom code is added only where
the construction workflow genuinely needs something ERPNext does not provide.

---

## What it does

### Sales and tendering
- Leads with inquiry type, date received, tender reference and requester
- Tender/bid registration with the customer's submission deadline
- A **separate internal estimation deadline**, enforced to fall on or before the
  customer deadline so there is time to review and approve before submission
- Named sales representative and estimation engineer per tender
- Quotations with per-quotation validity (not a fixed company-wide period)
- Variation orders raised against the originating project, priced and approved
  before execution

### Approvals
- Management approval workflows for quotations and sales invoices
- A controlled Sales → Projects handover workflow with a completion checklist
- Approval separated from preparation: the person who prepares a document
  cannot approve it

### Projects
- Internal project code, deliberately distinct from the customer's PO number
- Project manager, site supervisor and site address
- Task-driven progress using ERPNext's native calculation, with a ready-made
  construction project template (mobilisation → submittals → procurement →
  execution → testing → inspection → documentation → handover)
- Customer PO closure gated on project completion

### Procurement and delivery
- Project-linked purchasing that is **not** restricted to stock items —
  materials, services, subcontracting, consumables and rentals
- Procurement categories for reporting
- Delivery notes and a project completion certificate with a print format

### Billing and retention
- Billing types: standard, advance, progress, final and retention release
- Invoice status maintained automatically: Pending → Submitted → Approved →
  Paid → Overdue
- A retention register created automatically when an invoice withholds
  retention, ageing to *Due* on its release date
- A retention release flow that raises the release invoice, puts it through the
  normal approval workflow and closes the entry when it is submitted

### Warranty
- Warranty period, dates and terms, with the start date defaulting from project
  completion or handover
- A derived status (Not Started / Active / Expired) refreshed daily, so a
  warranty that lapses while nobody has the project open still reads correctly

### Inbound lead capture
- Enquiries arriving by **email** become leads automatically, with the
  conversation retained on the record
- A **WhatsApp** capture layer that activates when a WhatsApp connector is
  installed and configured
- Both channels share one sender resolver, so a customer who emails today and
  messages tomorrow lands on the same lead rather than a duplicate

### Reporting
Sixteen operational reports grouped into sales, project and finance sets,
covering tender deadlines, estimation workload, quotation expiry, pending
approvals, ongoing and in-progress projects, project commercials, procurement,
invoice status, receivables, advance and progress billing, retention, warranty,
variation orders and a customer 360 view — plus a management dashboard with
number cards and charts, and a dedicated workspace.

### Notifications
Deadline and approval alerts, delayed follow-up flagging, and an optional daily
summary of everything awaiting attention. Delivery is in-system by default and
switches to email once an outgoing mail account is configured.

---

## Requirements

| | |
|---|---|
| Frappe Framework | v16 |
| ERPNext | v16 |
| Python | 3.10+ |

---

## Installation

```bash
cd $PATH_TO_YOUR_BENCH

bench get-app https://github.com/sufiyanbuild/construction-crm-erpnext --branch version-16
bench --site your-site install-app jk_crm
bench --site your-site migrate
```

> `jk_crm` is the internal module identifier used throughout the codebase and by
> the bench commands. It is not a product name.

Installation configures custom fields, roles, workflows, notifications, the
project template, reports, dashboard, print format and workspace. It does **not**
create a company or any demo data.

---

## Configuration

After installing, open **JK CRM Settings** and set at least the default company.

| Setting | Purpose |
|---|---|
| Default Company | Company used by reports, number cards and charts. Nothing in the app hardcodes a company. |
| Notification Channel | System notification or email |
| Capture Leads from Email / WhatsApp | Enable or disable inbound capture |
| Reminder lead times | Bid, estimation and quotation expiry reminders |
| Retention Fallback Period | Used only when a sales order carries no retention period |
| Restrict Projects to Assigned Users | Optional project-level visibility, off by default |
| ZATCA Mode | See the note below |

### Optional integrations

**Email lead capture** requires an incoming Email Account in ERPNext.
**Email notifications** require a default outgoing Email Account; without one the
app keeps notifications in-system rather than queueing mail that cannot be sent.

**WhatsApp lead capture** requires a WhatsApp connector app and a WhatsApp
Business account configured with credentials from Meta. The capture layer in this
app stays inert until that is present, and stores no credentials of its own.

### ZATCA / Saudi e-invoicing

The app ships a **simulation** mode that generates a ZATCA-shaped QR payload and
invoice hash locally, for demonstration and development only.

> **This is not a compliant Saudi e-invoice.** Nothing is transmitted to ZATCA,
> and there is no clearance or reporting. Phase 2 integration requires a
> compliance app together with CSID onboarding credentials and is not implemented
> here. Do not use simulation output for live invoicing.

---

## Development

```bash
cd apps/jk_crm
pre-commit install
```

Pre-commit runs ruff, eslint, prettier and pyupgrade.

### Tests

```bash
bench --site your-site set-config allow_tests true
bench --site your-site run-tests --app jk_crm
```

The suite covers the business rules — deadline ordering, tender requirements,
variation orders, retention calculation and release, handover gating, warranty
dates and status, PO closure, invoice status, lead deduplication across channels
— plus guards that no company name leaks into shipped configuration.

### Project layout

```
jk_crm/
├── controllers.py        Business rules bound to ERPNext document events
├── retention.py          Retention release
├── tasks.py              Scheduled daily jobs
├── utils.py              Settings resolution and shared helpers
├── integrations/         Inbound lead capture (email, WhatsApp)
├── setup/                Install-time configuration, built per site
├── jk_crm/doctype/       Custom doctypes
└── tests/                Test suite
```

Configuration that depends on a company — reports, number cards, charts, the
dashboard and the workspace — is generated per site at install time rather than
shipped as fixtures, so no company name travels with the app.

---

## Contributing

Issues and pull requests are welcome. Please run the test suite and pre-commit
before opening a PR.

---

## License

MIT
