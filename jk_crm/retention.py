"""Retention release (BRD-18).

Retention was previously one-directional: entries were created when an invoice
withheld money, but nothing moved them to Released. This closes the loop.

The release itself is a normal Sales Invoice with Billing Type "Retention
Release", so it flows through the existing invoice approval workflow, the
existing payment tracking and the existing accounts - no parallel mechanism.
The Retention Entry simply points at it.
"""

import frappe
from frappe import _
from frappe.utils import flt, nowdate

RELEASABLE = ("Pending", "Due")


@frappe.whitelist()
def create_release_invoice(retention_entry, posting_date=None):
	"""Raise a Retention Release invoice for a retention entry.

	Returns the new invoice name. The invoice is left in draft so Finance can
	review it and put it through the normal approval workflow (BRD-34).
	"""
	entry = frappe.get_doc("JK Retention Entry", retention_entry)

	if entry.docstatus != 1:
		frappe.throw(_("Only a submitted Retention Entry can be released (BRD-18)."))
	if entry.status == "Released":
		frappe.throw(_("Retention {0} has already been released.").format(entry.name))
	if entry.status not in RELEASABLE:
		frappe.throw(
			_("Retention {0} is {1} and cannot be released.").format(entry.name, entry.status)
		)
	if entry.release_invoice:
		frappe.throw(
			_("Retention {0} already has release invoice {1}.").format(
				entry.name, entry.release_invoice
			)
		)
	if flt(entry.retention_amount) <= 0:
		frappe.throw(_("Retention {0} has no amount to release.").format(entry.name))

	invoice = frappe.new_doc("Sales Invoice")
	invoice.customer = entry.customer
	invoice.company = entry.company
	invoice.posting_date = posting_date or nowdate()
	invoice.set_posting_time = 1
	if entry.project:
		invoice.project = entry.project

	invoice.jk_billing_type = "Retention Release"
	# sales_invoice_validate zeroes retention on a release invoice, so this
	# invoice withholds nothing - it pays retention out.

	invoice.append(
		"items",
		{
			"item_name": _("Retention Release"),
			"description": _("Release of retention withheld on {0}").format(
				entry.sales_invoice or entry.project or entry.name
			),
			"qty": 1,
			"rate": flt(entry.retention_amount),
			"income_account": _release_income_account(entry),
		},
	)

	invoice.flags.ignore_permissions = True
	invoice.insert(ignore_permissions=True)

	entry.db_set("release_invoice", invoice.name, update_modified=False)

	frappe.msgprint(
		_("Retention Release invoice {0} created as draft for {1} {2}. "
		  "Submit it through the normal approval workflow to complete the release.").format(
			invoice.name, invoice.currency or "", flt(entry.retention_amount)
		),
		alert=True,
	)
	return invoice.name


def _release_income_account(entry):
	"""Use the company's default income account; let ERPNext validate the rest."""
	return frappe.db.get_value("Company", entry.company, "default_income_account")


def mark_released_from_invoice(doc, method=None):
	"""When a Retention Release invoice is submitted, close off its entry.

	Hooked on Sales Invoice on_submit, after the existing handlers.
	"""
	if doc.get("jk_billing_type") != "Retention Release":
		return

	for name in frappe.get_all(
		"JK Retention Entry",
		filters={"release_invoice": doc.name, "docstatus": 1},
		pluck="name",
	):
		frappe.db.set_value(
			"JK Retention Entry",
			name,
			{"status": "Released", "release_date": nowdate()},
			update_modified=False,
		)
		frappe.msgprint(
			_("Retention {0} marked as Released (BRD-18).").format(name), alert=True
		)


def reopen_released_from_invoice(doc, method=None):
	"""Cancelling a release invoice puts its retention back into play."""
	if doc.get("jk_billing_type") != "Retention Release":
		return

	for name in frappe.get_all(
		"JK Retention Entry",
		filters={"release_invoice": doc.name, "docstatus": 1},
		pluck="name",
	):
		entry = frappe.get_doc("JK Retention Entry", name)
		# Back to Due if its date has passed, otherwise Pending.
		status = "Due" if entry.release_due_date and entry.release_due_date <= nowdate() else "Pending"
		frappe.db.set_value(
			"JK Retention Entry",
			name,
			{"status": status, "release_invoice": None, "release_date": None},
			update_modified=False,
		)


def link_release_payment(doc, method=None):
	"""Record the Payment Entry that actually settled a retention release."""
	for ref in doc.get("references", []):
		if ref.reference_doctype != "Sales Invoice":
			continue
		for name in frappe.get_all(
			"JK Retention Entry",
			filters={"release_invoice": ref.reference_name, "docstatus": 1},
			pluck="name",
		):
			frappe.db.set_value(
				"JK Retention Entry",
				name,
				"payment_entry",
				doc.name if doc.docstatus == 1 else None,
				update_modified=False,
			)
