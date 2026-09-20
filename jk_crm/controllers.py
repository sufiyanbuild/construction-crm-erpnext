"""Business rules for BRD QN-2026-0010.

Each handler names the BRD clause it implements so the mapping stays auditable.
"""

import base64
import hashlib
import uuid

import frappe
from frappe import _
from frappe.utils import add_days, add_months, flt, getdate, now_datetime, nowdate

from jk_crm.utils import get_retention_fallback_days


# ---------------------------------------------------------------- Opportunity
def opportunity_validate(doc, method=None):
	"""BRD-04 estimation ownership, BRD-05 dual deadline rule."""
	if doc.get("jk_internal_estimation_deadline") and doc.get("jk_customer_bid_deadline"):
		if getdate(doc.jk_internal_estimation_deadline) > getdate(doc.jk_customer_bid_deadline):
			frappe.throw(
				_("Internal Estimation Deadline ({0}) cannot be after the Customer Bid Deadline ({1}). "
				  "The estimate must be finished in time for internal review and approval (BRD-05).")
				.format(doc.jk_internal_estimation_deadline, doc.jk_customer_bid_deadline)
			)

	if doc.get("jk_is_tender"):
		if not doc.get("jk_customer_bid_deadline"):
			frappe.throw(_("Customer Bid Submission Deadline is required for a tender (BRD-05)."))
		if not doc.get("jk_estimation_engineer"):
			frappe.throw(_("An Estimation Engineer must be assigned to every tender (BRD-04)."))

	if doc.get("jk_estimation_status") in ("Completed", "Submitted") and not doc.get("jk_estimation_completed_on"):
		doc.jk_estimation_completed_on = now_datetime()


# ------------------------------------------------------------------ Quotation
def quotation_validate(doc, method=None):
	"""BRD-13 variation orders, BRD-33 configurable validity."""
	if doc.get("jk_is_variation_order"):
		if not doc.get("jk_variation_project"):
			frappe.throw(_("A Variation Order must be linked to the originating Project (BRD-13)."))
		if not doc.get("jk_variation_reason"):
			frappe.throw(_("Reason for Variation is required on a Variation Order (BRD-13)."))

	# BRD-33: validity is per-quotation, never a fixed global period - but it
	# must still be in the future or the expiry notification is meaningless.
	if doc.get("valid_till") and getdate(doc.valid_till) < getdate(doc.transaction_date):
		frappe.throw(_("Quotation validity ({0}) cannot be before the quotation date ({1}).")
			.format(doc.valid_till, doc.transaction_date))


# ---------------------------------------------------------------- Sales Order
def sales_order_validate(doc, method=None):
	"""BRD-18 retention terms captured at order stage."""
	if doc.get("jk_has_retention"):
		if not flt(doc.get("jk_retention_percentage")):
			frappe.throw(_("Retention % is required when retention is applicable (BRD-18)."))
		doc.jk_retention_amount = flt(doc.grand_total) * flt(doc.jk_retention_percentage) / 100.0
	else:
		doc.jk_retention_amount = 0


# -------------------------------------------------------------------- Project
def project_validate(doc, method=None):
	"""BRD-09 project code, BRD-10 PM, BRD-11 handover, BRD-23 warranty."""
	# BRD-09: a project code distinct from the customer's PO number.
	if not doc.get("jk_project_code"):
		doc.jk_project_code = frappe.model.naming.make_autoname("PRJ-.YY.-.####")

	# BRD-10
	if not doc.get("jk_project_manager"):
		frappe.msgprint(_("No Project Manager assigned yet (BRD-10)."), indicator="orange", alert=True)

	# BRD-11
	if doc.get("jk_handover_status") == "Handover Accepted":
		if not doc.get("jk_handover_to"):
			frappe.throw(_("'Accepted By (Projects)' is required to complete handover (BRD-11)."))
		if not doc.get("jk_handover_date"):
			doc.jk_handover_date = nowdate()
		pending = [d.activity for d in doc.get("jk_handover_checklist", []) if not d.completed]
		if pending:
			frappe.throw(_("Handover cannot be accepted while checklist items are open: {0}")
				.format(", ".join(pending)))

	# BRD-23 warranty
	_apply_warranty(doc)

	# BRD-15 completion certificate
	_apply_completion(doc)

	# BRD-32: PO closure follows project completion, never precedes it.
	if doc.get("jk_customer_po_status") == "Closed" and doc.status != "Completed":
		frappe.throw(_("The customer Purchase Order can only be closed once the Project is Completed (BRD-32)."))


def _apply_warranty(doc):
	"""BRD-23: warranty dates, defaulting and status.

	The BRD ties warranty to project completion, so when the warranty is
	applicable but no start date has been entered we take it from the handover
	or completion date rather than leaving the field blank and the end date
	uncomputable.
	"""
	if not doc.get("jk_has_warranty"):
		doc.jk_warranty_end_date = None
		doc.jk_warranty_status = "Not Applicable"
		return

	if not doc.get("jk_warranty_start_date"):
		# Completion first, then handover acceptance - both mark the point the
		# customer takes the asset on.
		fallback = doc.get("jk_completion_date") or doc.get("jk_handover_date")
		if fallback:
			doc.jk_warranty_start_date = fallback

	if not doc.get("jk_warranty_period_months"):
		frappe.throw(
			_("Warranty Period (Months) is required when a warranty applies (BRD-23).")
		)

	if not doc.get("jk_warranty_start_date"):
		frappe.throw(
			_("Warranty Start Date is required when a warranty applies. It defaults from "
			  "the Completion Date or Handover Date once either is set (BRD-23).")
		)

	doc.jk_warranty_end_date = add_months(
		getdate(doc.jk_warranty_start_date), int(doc.jk_warranty_period_months)
	)

	today = getdate(nowdate())
	if getdate(doc.jk_warranty_start_date) > today:
		doc.jk_warranty_status = "Not Started"
	elif getdate(doc.jk_warranty_end_date) < today:
		doc.jk_warranty_status = "Expired"
	else:
		doc.jk_warranty_status = "Active"


def _apply_completion(doc):
	"""BRD-15: issue a completion certificate number once the project completes."""
	if doc.get("status") != "Completed":
		return

	if not doc.get("jk_completion_date"):
		doc.jk_completion_date = nowdate()

	if not doc.get("jk_completion_certificate_no"):
		doc.jk_completion_certificate_no = frappe.model.naming.make_autoname(
			"JK-CC-.YYYY.-.####"
		)


# --------------------------------------------------------------- Sales Invoice
def sales_invoice_validate(doc, method=None):
	"""BRD-16 status, BRD-17 billing type, BRD-18 retention."""
	if doc.get("jk_billing_type") == "Retention Release":
		doc.jk_retention_percentage = 0
		doc.jk_retention_amount = 0
	elif flt(doc.get("jk_retention_percentage")):
		doc.jk_retention_amount = flt(doc.grand_total) * flt(doc.jk_retention_percentage) / 100.0
		if not doc.get("jk_retention_release_date"):
			days = 0
			if doc.get("project"):
				so = frappe.db.get_value("Sales Order",
					{"project": doc.project, "docstatus": 1}, "jk_retention_period_days")
				days = int(so or 0)
			doc.jk_retention_release_date = add_days(
				getdate(doc.posting_date), days or get_retention_fallback_days()
			)
	else:
		doc.jk_retention_amount = 0

	if doc.docstatus == 0:
		doc.jk_invoice_status = "Pending"


def sales_invoice_on_submit(doc, method=None):
	"""BRD-16 status, BRD-18 retention register, BRD-24 ZATCA (demo)."""
	# A workflow-approved invoice records 'Approved'; a direct submit records 'Submitted'.
	state = "Approved" if doc.get("workflow_state") == "Approved" else "Submitted"
	doc.db_set("jk_invoice_status", state, update_modified=False)
	_simulate_zatca(doc)

	if flt(doc.get("jk_retention_amount")) > 0:
		_create_retention_entry(doc)


def _is_ksa(company):
	"""This site hosts non-Saudi companies too; ZATCA applies only to KSA ones."""
	return frappe.db.get_value("Company", company, "country") == "Saudi Arabia"


def sales_invoice_on_cancel(doc, method=None):
	doc.db_set("jk_invoice_status", "Pending", update_modified=False)
	for name in frappe.get_all("JK Retention Entry",
			filters={"sales_invoice": doc.name, "docstatus": 1}, pluck="name"):
		frappe.get_doc("JK Retention Entry", name).cancel()


def _create_retention_entry(doc):
	"""BRD-18: retention is registered so it can be tracked and released later."""
	if frappe.db.exists("JK Retention Entry", {"sales_invoice": doc.name, "docstatus": 1}):
		return
	entry = frappe.get_doc({
		"doctype": "JK Retention Entry",
		"project": doc.get("project"),
		"customer": doc.customer,
		"company": doc.company,
		"sales_invoice": doc.name,
		"retention_amount": flt(doc.jk_retention_amount),
		"release_due_date": doc.jk_retention_release_date,
		"status": "Pending",
		"remarks": f"Withheld {doc.jk_retention_percentage}% from {doc.name}.",
	})
	entry.insert(ignore_permissions=True)
	entry.submit()
	frappe.msgprint(
		_("Retention Entry {0} created for {1} {2} (BRD-18).")
		.format(entry.name, doc.currency, flt(doc.jk_retention_amount)), alert=True
	)


def _simulate_zatca(doc):
	"""BRD-24 - ZATCA Phase 1 TLV QR, generated locally for the demo.

	The TLV structure below is the real ZATCA seller/VAT/timestamp/total/VAT
	payload. Phase 2 clearance requires the compliance app plus CSID onboarding
	credentials, which are deliberately out of scope for this demo site.
	"""
	if not _is_ksa(doc.company):
		doc.db_set("jk_zatca_status", "Not Applicable", update_modified=False)
		return

	seller = frappe.db.get_value("Company", doc.company, "company_name") or doc.company
	vat_no = frappe.db.get_value("Company", doc.company, "tax_id") or "000000000000000"
	# ZATCA requires a zero-padded ISO-8601 stamp; posting_time arrives as a
	# timedelta/str that can carry microseconds and a single-digit hour.
	raw_time = str(doc.get("posting_time") or "00:00:00").split(".")[0]
	hh, mm, ss = (raw_time.split(":") + ["0", "0", "0"])[:3]
	stamp = f"{doc.posting_date}T{int(hh):02d}:{int(mm):02d}:{int(ss):02d}Z"
	vat_amount = flt(doc.grand_total) - flt(doc.net_total)

	def tlv(tag, value):
		raw = str(value).encode("utf-8")
		return bytes([tag, len(raw)]) + raw

	payload = (
		tlv(1, seller) + tlv(2, vat_no) + tlv(3, stamp)
		+ tlv(4, f"{flt(doc.grand_total):.2f}") + tlv(5, f"{flt(vat_amount):.2f}")
	)
	qr = base64.b64encode(payload).decode()
	inv_hash = base64.b64encode(
		hashlib.sha256(f"{doc.name}{doc.grand_total}{doc.posting_date}".encode()).digest()
	).decode()

	doc.db_set({
		"jk_zatca_uuid": str(uuid.uuid4()),
		"jk_zatca_hash": inv_hash,
		"jk_zatca_qr": qr,
		"jk_zatca_status": "Simulated (Demo)",
	}, update_modified=False)


# -------------------------------------------------------------- Payment Entry
def payment_entry_on_submit(doc, method=None):
	"""BRD-16 / BRD-19: paid status flows back to the invoice."""
	_refresh_invoices_from_payment(doc)


def payment_entry_on_cancel(doc, method=None):
	_refresh_invoices_from_payment(doc)


def _refresh_invoices_from_payment(doc):
	for ref in doc.get("references", []):
		if ref.reference_doctype != "Sales Invoice":
			continue
		refresh_invoice_status(ref.reference_name)


def refresh_invoice_status(name):
	inv = frappe.db.get_value("Sales Invoice", name,
		["docstatus", "outstanding_amount", "due_date", "jk_invoice_status"], as_dict=True)
	if not inv or inv.docstatus != 1:
		return
	# An explicit 'Approved' set by the workflow is not overwritten by 'Submitted'.
	if flt(inv.outstanding_amount) <= 0:
		status = "Paid"
	elif inv.due_date and getdate(inv.due_date) < getdate(nowdate()):
		status = "Overdue"
	elif inv.jk_invoice_status == "Approved":
		status = "Approved"
	else:
		status = "Submitted"
	if status != inv.jk_invoice_status:
		frappe.db.set_value("Sales Invoice", name, "jk_invoice_status", status, update_modified=False)
