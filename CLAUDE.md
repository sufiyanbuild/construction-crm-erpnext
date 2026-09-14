# CLAUDE.md — jk_crm Development Rules

Permanent working rules for this repository. They apply to every task, every
session, and every contributor — human or agent. Read this before touching code.

---

## 1. What this project is

`jk_crm` is a **reusable Frappe / ERPNext v16 application**. It implements the
CRM and project lifecycle described in BRD **QN-2026-0010** for JK Consultancies:
lead → tender → quotation → sales order → project → procurement → delivery →
progress and retention invoicing → payment → variation orders → handover →
warranty → closure.

It is built to be installed on **any** ERPNext v16 site, not just the local demo
site. That single fact drives most of the rules below: nothing may depend on
one machine, one database, or one manually-clicked UI change.

**Repository:** `git@github.com:sufiyanbuild/construction-crm-erpnext.git`
**Primary branch:** `version-16` (Frappe convention — this is not `main`, and that is deliberate)

### House conventions already established

- Every custom field is prefixed `jk_`; every role, workflow, notification and
  report is prefixed `JK `. Ownership of a customisation must be unambiguous at
  a glance.
- Every business rule names the BRD clause it implements in a comment or
  docstring, so the requirement-to-code mapping stays auditable.
- Setup functions are **idempotent** — they guard with `frappe.db.exists` and can
  be re-run safely.
- Configuration travels with the app through `fixtures` in `hooks.py`. If a
  change only exists in the UI of one site, it does not exist.

---

## 2. Boundaries — what must never be touched

### Never modify Frappe core or ERPNext core

Do not edit anything under `apps/frappe` or `apps/erpnext` unless a maintainer
explicitly authorises that specific change. Core edits are silently destroyed by
the next `bench update`, and they make this app unshippable to a client server.

When core behaviour is wrong for our use case, extend it from `jk_crm` instead:
`doc_events` hooks, `override_whitelisted_methods`, `extend_doctype_class`,
custom fields, or a `permission_query_conditions` hook.

### Never modify production

No schema changes, no data fixes, no `bench` commands against a production site.
Production changes go through a reviewed deployment, never an interactive session.

### Ask before destructive operations

Stop and get explicit approval before anything that loses work or is hard to
reverse — `git reset --hard`, `git rebase`, history rewrites, `bench drop-site`,
`bench --force restore`, `frappe.delete_doc` on real data, dropping columns,
truncating tables, deleting branches, or removing files you did not create.
Describe what will be lost, then wait for a clear yes.

---

## 3. Design rules

### Prefer standard ERPNext before customising

ERPNext already ships payment terms, taxes, approval workflows, project tasks,
subscriptions, and a great deal more. **If a requirement can be met with standard
ERPNext functionality, say so before writing custom code** — explain which stock
feature covers it and what configuring it would look like. Custom code is a cost
paid at every future upgrade; only pay it when the standard feature genuinely
cannot do the job.

### Inspect before creating

Before adding a DocType, field, report, or workflow, search for what already
exists — in ERPNext, in Frappe, and in `jk_crm` itself. Duplicate concepts split
data across two places and are expensive to merge later. Extending an existing
DocType is almost always better than introducing a parallel one.

### Client Script is for UI behaviour only

Client-side code may show and hide fields, set defaults, filter link queries,
add form buttons, and improve the editing experience. That is all.

### Business-critical validation must be server-side

Anything that protects data integrity — required fields, cross-field rules,
amount and date calculations, status transitions, permission checks — belongs in
a server-side `validate` / `on_submit` / `on_cancel` handler. Client-side checks
are a convenience for the user and are trivially bypassed via the API, `bench
console`, data import, or a direct REST call. If the rule matters, it is enforced
on the server.

### Reusable business logic lives inside jk_crm

Logic belongs in versioned Python in this app — `jk_crm/controllers.py`,
`jk_crm/tasks.py`, `jk_crm/setup/`, or a DocType controller. Not in a Server
Script, not in a one-off console snippet, not in a fixture, not on one site only.
Code in the repo is reviewable, testable, diffable, and deployable everywhere.

### Avoid Server Scripts unless explicitly approved

Server Scripts live in the database, not in git. They escape code review, escape
tests, and do not travel with the app. Use versioned Python instead. Where a
Server Script is genuinely the right answer, get approval first and record why.

### Preserve Frappe / ERPNext naming and UX conventions

`snake_case` fieldnames, `Title Case` labels, standard naming series, standard
section and column break layout, standard status and workflow patterns, standard
list view and dashboard idioms. A user who knows ERPNext should need no
retraining to use this app, and a developer who knows Frappe should find the code
where they expect it.

---

## 4. Testing

**Every significant feature requires tests.** A feature is significant if it
enforces a business rule, calculates a monetary amount, changes a document's
status, or creates or cancels another document.

Tests live beside the code they cover (for example
`jk_crm/jk_crm/doctype/jk_retention_entry/test_jk_retention_entry.py`) and run
with:

```bash
bench --site <site> run-tests --app jk_crm
bench --site <site> run-tests --doctype "JK Retention Entry"
```

**Run the relevant tests before committing.** If tests fail, report the failure
and the output — never describe work as finished while its tests are red.

---

## 5. Git workflow

### Check git status before every task

Start by knowing what is already modified, staged, or untracked. Never begin work
on top of someone else's uncommitted changes without understanding them first.

### Use a feature branch for significant features

Branch from `version-16` for anything beyond a trivial fix:

```bash
git checkout -b feature/<short-description>
```

Small, self-contained commits with clear messages. Merge back through review.

### Never force-push

No `git push --force`, no `--force-with-lease`, on any shared branch. If history
looks wrong, stop and ask — force-pushing destroys other people's work silently
and is frequently unrecoverable.

### Never commit secrets or local runtime data

Never commit passwords, API keys, tokens, private keys, certificates, `.env`
files, `site_config.json`, `common_site_config.json`, database dumps (`*.sql`,
`*.sql.gz`), backups, logs, `__pycache__`, `*.pyc`, `node_modules`, editor
directories, or anything else specific to one machine or one site.

Real credentials belong in site config on the server, read at runtime via
`frappe.conf` — never in the repository. If a secret is ever committed, treat it
as compromised: rotate it first, then clean the history.

### Review before committing

Read `git diff` (unstaged) and `git diff --cached` (staged) before every commit.
Confirm the staged set is exactly what you intend — no stray debug prints, no
commented-out experiments, no unrelated files swept in by a broad `git add`.

---

## 6. Reporting

After a successful implementation, report:

- **Files changed** — the actual list, not a summary
- **Tests run** — the exact commands
- **Test results** — pass and fail counts; paste the output if anything failed
- **Branch**
- **Commit hash**
- **GitHub push result** — confirmed against the remote, not merely attempted

Report outcomes honestly. If a step was skipped, say so and say why. If part of
the work is incomplete or blocked, state which part, rather than letting a
summary imply the whole task landed.
