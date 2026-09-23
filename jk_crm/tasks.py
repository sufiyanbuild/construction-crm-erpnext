"""Scheduled jobs for BRD QN-2026-0010 (BRD-06, BRD-16, BRD-18, BRD-23)."""

import frappe
from frappe.utils import add_days, getdate, nowdate

from jk_crm.controllers import refresh_invoice_status
from jk_crm.utils import get_default_company, get_setting


def daily():
	update_invoice_statuses()
	update_retention_status()
	update_warranty_status()
	flag_delayed_followups()
	send_pending_digest()


def update_invoice_statuses():
	"""BRD-16: keep Pending / Submitted / Approved / Paid / Overdue accurate."""
	names = frappe.get_all("Sales Invoice", filters={"docstatus": 1}, pluck="name")
	for name in names:
		refresh_invoice_status(name)
	frappe.db.commit()


def update_retention_status():
	"""BRD-18: retention becomes Due once the agreed period has elapsed."""
	due = frappe.get_all("JK Retention Entry",
		filters={"docstatus": 1, "status": "Pending", "release_due_date": ["<=", nowdate()]},
		pluck="name")
	for name in due:
		frappe.db.set_value("JK Retention Entry", name, "status", "Due")
	if due:
		frappe.db.commit()
	return due


def update_warranty_status():
	"""BRD-23: keep Not Started / Active / Expired accurate as dates pass.

	Warranty status is derived on save, but a project nobody opens would sit at
	Active for years after expiry. This ages them without touching anything
	else on the document.
	"""
	today = getdate(nowdate())
	changed = []

	projects = frappe.get_all(
		"Project",
		filters={"jk_has_warranty": 1},
		fields=["name", "jk_warranty_start_date", "jk_warranty_end_date", "jk_warranty_status"],
	)
	for project in projects:
		if not project.jk_warranty_start_date or not project.jk_warranty_end_date:
			continue
		if getdate(project.jk_warranty_start_date) > today:
			status = "Not Started"
		elif getdate(project.jk_warranty_end_date) < today:
			status = "Expired"
		else:
			status = "Active"

		if status != project.jk_warranty_status:
			frappe.db.set_value(
				"Project", project.name, "jk_warranty_status", status, update_modified=False
			)
			changed.append(project.name)

	if changed:
		frappe.db.commit()
	return changed


def flag_delayed_followups():
	"""BRD-06: surface leads and opportunities nobody has touched.

	The idle threshold is configurable because the BRD does not fix one; it
	defaults to 7 days and is marked pending client confirmation in settings.
	"""
	idle_days = int(get_setting("followup_idle_days", default=7) or 7)
	cutoff = add_days(nowdate(), -idle_days)

	stale_leads = frappe.get_all(
		"Lead",
		filters={"status": ["in", ["Lead", "Open", "Replied"]], "modified": ["<", cutoff]},
		fields=["name", "lead_name", "lead_owner", "modified"],
		limit=50,
	)
	stale_opps = frappe.get_all(
		"Opportunity",
		filters={"status": ["in", ["Open", "Quotation"]], "modified": ["<", cutoff]},
		fields=["name", "party_name", "jk_estimation_engineer", "modified"],
		limit=50,
	)

	for lead in stale_leads:
		if lead.lead_owner:
			_notify(
				lead.lead_owner,
				f"Lead {lead.lead_name or lead.name} has had no activity for {idle_days} days",
				"Lead",
				lead.name,
			)

	for opp in stale_opps:
		if opp.jk_estimation_engineer:
			_notify(
				opp.jk_estimation_engineer,
				f"Opportunity {opp.name} ({opp.party_name}) has had no activity for {idle_days} days",
				"Opportunity",
				opp.name,
			)

	return {"leads": len(stale_leads), "opportunities": len(stale_opps)}


def send_pending_digest():
	"""BRD-06: one daily summary of what needs attention, to JK Management."""
	if not get_setting("send_daily_digest", default=1):
		return None

	company = get_default_company()
	company_filter = {"company": company} if company else {}

	pending_quotations = frappe.db.count(
		"Quotation", {"workflow_state": "Pending", **company_filter}
	)
	pending_invoices = frappe.db.count(
		"Sales Invoice", {"workflow_state": "Pending", **company_filter}
	)
	overdue_invoices = frappe.db.count(
		"Sales Invoice", {"jk_invoice_status": "Overdue", "docstatus": 1, **company_filter}
	)
	retention_due = frappe.db.count("JK Retention Entry", {"status": "Due", "docstatus": 1})
	tenders_closing = frappe.db.count(
		"Opportunity",
		{
			"jk_is_tender": 1,
			"status": ["in", ["Open", "Quotation"]],
			"jk_customer_bid_deadline": ["between", [nowdate(), add_days(nowdate(), 3)]],
		},
	)
	pending_handovers = frappe.db.count("Project", {"jk_handover_status": "Pending Handover"})

	total = (
		pending_quotations + pending_invoices + overdue_invoices
		+ retention_due + tenders_closing + pending_handovers
	)
	if not total:
		return None

	lines = [
		f"Quotations awaiting approval: {pending_quotations}",
		f"Invoices awaiting approval: {pending_invoices}",
		f"Overdue invoices: {overdue_invoices}",
		f"Retention due for release: {retention_due}",
		f"Tender deadlines within 3 days: {tenders_closing}",
		f"Projects awaiting handover: {pending_handovers}",
	]
	message = "Daily CRM summary\n\n" + "\n".join(lines)

	for user in _users_with_role("JK Management"):
		_notify(user, message, None, None, subject="Daily CRM summary")

	frappe.db.commit()
	return {"recipients": len(_users_with_role("JK Management")), "total": total}


def _users_with_role(role):
	return frappe.get_all(
		"Has Role",
		filters={"role": role, "parenttype": "User"},
		pluck="parent",
	)


def _notify(user, message, doctype=None, name=None, subject=None):
	"""Raise an in-system notification, honouring the configured channel."""
	if not frappe.db.exists("User", user):
		return
	try:
		notification = frappe.new_doc("Notification Log")
		notification.subject = subject or message[:140]
		notification.email_content = message
		notification.for_user = user
		notification.type = "Alert"
		if doctype and name:
			notification.document_type = doctype
			notification.document_name = name
		notification.flags.ignore_permissions = True
		notification.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="jk_crm notification failed", message=frappe.get_traceback())
