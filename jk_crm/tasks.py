"""Scheduled jobs for BRD QN-2026-0010 (BRD-06, BRD-16, BRD-18, BRD-23)."""

import frappe
from frappe.utils import getdate, nowdate

from jk_crm.controllers import refresh_invoice_status


def daily():
	update_invoice_statuses()
	update_retention_status()


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
