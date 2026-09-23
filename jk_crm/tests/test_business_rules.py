"""Tests for the BRD business rules in jk_crm.controllers.

These exercise the validators directly against unsaved documents. That is
deliberate: the rules are pure field logic, so testing them this way covers the
decision branches without standing up a company, chart of accounts, items and
customers first - which would make the suite slow, fragile and dependent on demo
data that is not present on a client server.

Rules that genuinely need the database (retention entry creation, invoice status
refresh) are covered in test_retention.py instead.
"""

import unittest

import frappe
from frappe.utils import add_days, add_months, getdate, nowdate

from jk_crm.controllers import (
	opportunity_validate,
	project_validate,
	quotation_validate,
	sales_invoice_validate,
	sales_order_validate,
)


def doc(doctype, **fields):
	"""An unsaved in-memory document; enough for a validator to read."""
	return frappe.get_doc({"doctype": doctype, **fields})


class TestOpportunityRules(unittest.TestCase):
	"""BRD-04 estimation ownership, BRD-05 dual deadline rule."""

	def test_internal_deadline_after_customer_deadline_is_rejected(self):
		# The core BRD-05 rule: estimating must finish before the bid goes out.
		d = doc(
			"Opportunity",
			jk_internal_estimation_deadline="2026-09-10 17:00:00",
			jk_customer_bid_deadline="2026-09-05 16:00:00",
		)
		with self.assertRaises(frappe.ValidationError):
			opportunity_validate(d)

	def test_internal_deadline_before_customer_deadline_is_accepted(self):
		d = doc(
			"Opportunity",
			jk_internal_estimation_deadline="2026-08-30 17:00:00",
			jk_customer_bid_deadline="2026-09-05 16:00:00",
		)
		opportunity_validate(d)

	def test_equal_deadlines_are_accepted(self):
		# Boundary: same instant is tight but not a violation.
		stamp = "2026-09-05 16:00:00"
		d = doc(
			"Opportunity",
			jk_internal_estimation_deadline=stamp,
			jk_customer_bid_deadline=stamp,
		)
		opportunity_validate(d)

	def test_tender_without_bid_deadline_is_rejected(self):
		d = doc("Opportunity", jk_is_tender=1, jk_estimation_engineer="Administrator")
		with self.assertRaises(frappe.ValidationError):
			opportunity_validate(d)

	def test_tender_without_estimation_engineer_is_rejected(self):
		# BRD-04: every tender has a named owner for the estimate.
		d = doc(
			"Opportunity",
			jk_is_tender=1,
			jk_customer_bid_deadline="2026-09-05 16:00:00",
		)
		with self.assertRaises(frappe.ValidationError):
			opportunity_validate(d)

	def test_non_tender_needs_neither(self):
		opportunity_validate(doc("Opportunity", jk_is_tender=0))

	def test_completion_timestamp_is_stamped_once_estimation_completes(self):
		d = doc("Opportunity", jk_estimation_status="Completed")
		opportunity_validate(d)
		self.assertTrue(d.jk_estimation_completed_on)

	def test_completion_timestamp_not_stamped_while_in_progress(self):
		d = doc("Opportunity", jk_estimation_status="In Progress")
		opportunity_validate(d)
		self.assertFalse(d.get("jk_estimation_completed_on"))


class TestQuotationRules(unittest.TestCase):
	"""BRD-13 variation orders, BRD-33 configurable validity."""

	def test_variation_order_requires_project(self):
		d = doc("Quotation", jk_is_variation_order=1, jk_variation_reason="Extra tank")
		with self.assertRaises(frappe.ValidationError):
			quotation_validate(d)

	def test_variation_order_requires_reason(self):
		d = doc("Quotation", jk_is_variation_order=1, jk_variation_project="PROJ-0001")
		with self.assertRaises(frappe.ValidationError):
			quotation_validate(d)

	def test_complete_variation_order_is_accepted(self):
		quotation_validate(doc(
			"Quotation",
			jk_is_variation_order=1,
			jk_variation_project="PROJ-0001",
			jk_variation_reason="Additional water storage tank",
		))

	def test_validity_before_quotation_date_is_rejected(self):
		d = doc("Quotation", transaction_date="2026-09-01", valid_till="2026-08-25")
		with self.assertRaises(frappe.ValidationError):
			quotation_validate(d)

	def test_validity_after_quotation_date_is_accepted(self):
		# BRD-33: validity varies per opportunity, so any future date is valid.
		quotation_validate(doc(
			"Quotation", transaction_date="2026-09-01", valid_till="2026-10-15"
		))


class TestSalesOrderRetention(unittest.TestCase):
	"""BRD-18: retention terms agreed at order stage."""

	def test_retention_amount_is_calculated_from_percentage(self):
		d = doc(
			"Sales Order",
			jk_has_retention=1,
			jk_retention_percentage=10,
			grand_total=250000,
		)
		sales_order_validate(d)
		self.assertEqual(d.jk_retention_amount, 25000.0)

	def test_retention_flag_without_percentage_is_rejected(self):
		d = doc("Sales Order", jk_has_retention=1, grand_total=250000)
		with self.assertRaises(frappe.ValidationError):
			sales_order_validate(d)

	def test_retention_amount_is_zeroed_when_not_applicable(self):
		d = doc(
			"Sales Order",
			jk_has_retention=0,
			jk_retention_percentage=10,
			jk_retention_amount=999,
			grand_total=250000,
		)
		sales_order_validate(d)
		self.assertEqual(d.jk_retention_amount, 0)

	def test_fractional_percentage_is_handled(self):
		d = doc(
			"Sales Order", jk_has_retention=1, jk_retention_percentage=7.5, grand_total=100000
		)
		sales_order_validate(d)
		self.assertEqual(d.jk_retention_amount, 7500.0)


class TestProjectRules(unittest.TestCase):
	"""BRD-09 code, BRD-11 handover, BRD-23 warranty, BRD-32 PO closure."""

	def test_project_code_is_generated_when_absent(self):
		d = doc("Project", project_name="Test", status="Open")
		project_validate(d)
		self.assertTrue(d.jk_project_code)
		self.assertTrue(d.jk_project_code.startswith("PRJ-"))

	def test_existing_project_code_is_preserved(self):
		d = doc("Project", project_name="Test", status="Open", jk_project_code="PRJ-RDA-0442")
		project_validate(d)
		self.assertEqual(d.jk_project_code, "PRJ-RDA-0442")

	def test_handover_acceptance_requires_accepting_user(self):
		d = doc("Project", status="Open", jk_handover_status="Handover Accepted")
		with self.assertRaises(frappe.ValidationError):
			project_validate(d)

	def test_handover_blocked_while_checklist_items_are_open(self):
		d = doc(
			"Project",
			status="Open",
			jk_handover_status="Handover Accepted",
			jk_handover_to="Administrator",
			jk_handover_checklist=[
				{"activity": "Drawings handed over", "completed": 1},
				{"activity": "Site access arranged", "completed": 0},
			],
		)
		with self.assertRaises(frappe.ValidationError):
			project_validate(d)

	def test_handover_accepted_when_checklist_is_complete(self):
		d = doc(
			"Project",
			status="Open",
			jk_handover_status="Handover Accepted",
			jk_handover_to="Administrator",
			jk_handover_checklist=[{"activity": "Drawings handed over", "completed": 1}],
		)
		project_validate(d)
		self.assertEqual(getdate(d.jk_handover_date), getdate(nowdate()))

	def test_warranty_end_date_is_derived_from_start_and_period(self):
		d = doc(
			"Project",
			status="Open",
			jk_has_warranty=1,
			jk_warranty_start_date="2026-09-15",
			jk_warranty_period_months=24,
		)
		project_validate(d)
		self.assertEqual(getdate(d.jk_warranty_end_date), add_months(getdate("2026-09-15"), 24))

	def test_customer_po_cannot_close_before_project_completes(self):
		# BRD-32: closure follows completion, never precedes it.
		d = doc("Project", status="Open", jk_customer_po_status="Closed")
		with self.assertRaises(frappe.ValidationError):
			project_validate(d)

	def test_customer_po_closes_once_project_is_completed(self):
		d = doc("Project", status="Completed", jk_customer_po_status="Closed")
		project_validate(d)


class TestSalesInvoiceRules(unittest.TestCase):
	"""BRD-16 status, BRD-17 billing type, BRD-18 retention."""

	def test_retention_amount_is_calculated_from_percentage(self):
		d = doc(
			"Sales Invoice",
			jk_billing_type="Progress",
			jk_retention_percentage=10,
			grand_total=90275,
			posting_date="2026-09-15",
			docstatus=0,
		)
		sales_invoice_validate(d)
		self.assertAlmostEqual(d.jk_retention_amount, 9027.5, places=2)

	def test_release_date_is_set_when_retention_applies(self):
		d = doc(
			"Sales Invoice",
			jk_retention_percentage=10,
			grand_total=100000,
			posting_date="2026-09-15",
			docstatus=0,
		)
		sales_invoice_validate(d)
		self.assertTrue(d.jk_retention_release_date)
		# With no Sales Order period, the configurable fallback applies (BRD-18).
		self.assertGreater(getdate(d.jk_retention_release_date), getdate("2026-09-15"))

	def test_retention_release_invoice_withholds_nothing(self):
		# A Retention Release invoice pays retention out; it must not withhold again.
		d = doc(
			"Sales Invoice",
			jk_billing_type="Retention Release",
			jk_retention_percentage=10,
			grand_total=25484,
			posting_date="2026-09-15",
			docstatus=0,
		)
		sales_invoice_validate(d)
		self.assertEqual(d.jk_retention_amount, 0)
		self.assertEqual(d.jk_retention_percentage, 0)

	def test_draft_invoice_starts_pending(self):
		d = doc("Sales Invoice", grand_total=1000, posting_date="2026-09-15", docstatus=0)
		sales_invoice_validate(d)
		self.assertEqual(d.jk_invoice_status, "Pending")

	def test_no_retention_zeroes_the_amount(self):
		d = doc(
			"Sales Invoice",
			jk_retention_percentage=0,
			jk_retention_amount=500,
			grand_total=1000,
			posting_date="2026-09-15",
			docstatus=0,
		)
		sales_invoice_validate(d)
		self.assertEqual(d.jk_retention_amount, 0)


class TestConfiguration(unittest.TestCase):
	"""Phase 1: nothing site-specific may be hardcoded in the app."""

	def test_settings_doctype_exists(self):
		self.assertTrue(frappe.db.exists("DocType", "JK CRM Settings"))

	def test_shipped_fixtures_carry_no_company(self):
		import glob
		import os

		import jk_crm

		fixtures = os.path.join(os.path.dirname(jk_crm.__file__), "fixtures", "*.json")
		offenders = []
		for path in glob.glob(fixtures):
			with open(path) as handle:
				if "JK Demo Contracting" in handle.read():
					offenders.append(os.path.basename(path))
		self.assertEqual(offenders, [], f"company name leaked into fixtures: {offenders}")

	def test_retention_fallback_is_configurable(self):
		from jk_crm.utils import get_retention_fallback_days

		self.assertIsInstance(get_retention_fallback_days(), int)
		self.assertGreater(get_retention_fallback_days(), 0)

	def test_notification_channel_never_returns_email_without_an_account(self):
		from jk_crm.utils import get_notification_channel, has_outgoing_email

		if not has_outgoing_email():
			self.assertEqual(get_notification_channel(), "System Notification")
