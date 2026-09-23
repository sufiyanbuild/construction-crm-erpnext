# Copyright (c) 2026, JK Consultancies and Contributors
# See license.txt
"""Database-backed tests for the retention register (BRD-18).

Deliberately a plain TestCase rather than Frappe's IntegrationTestCase: that
base class auto-generates test records for every linked doctype, which walks
JK Retention Entry -> Project -> erpnext...test_project -> test_project_template
and fails inside ERPNext's own test fixtures. We create exactly the records we
need instead, and clean them up.
"""

import unittest

import frappe
from frappe.utils import add_days, nowdate

from jk_crm.tasks import update_retention_status

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []

TEST_MARK = "Created by jk_crm automated test."


class TestJKRetentionEntry(unittest.TestCase):
	"""The retention register must submit, age Pending -> Due, and cancel."""

	@classmethod
	def setUpClass(cls):
		# project and customer are mandatory on the doctype. Rather than
		# fabricating a company, chart of accounts and customer just to insert a
		# row, reuse whatever the site already has and skip cleanly when a bare
		# site has none - the schema tests below still run everywhere.
		from jk_crm.tests._helpers import consistent_party

		cls.company, cls.customer, cls.project = consistent_party()
		cls.has_masters = bool(cls.company and cls.project and cls.customer)

	def tearDown(self):
		# Leave the site as we found it - these run against a real database.
		for name in frappe.get_all(
			"JK Retention Entry", filters={"remarks": TEST_MARK}, pluck="name"
		):
			doc = frappe.get_doc("JK Retention Entry", name)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("JK Retention Entry", name, force=1, ignore_permissions=True)
		frappe.db.commit()

	def _entry(self, due_date, amount=1000):
		if not self.has_masters:
			self.skipTest("site has no Company/Project/Customer to attach retention to")
		entry = frappe.get_doc({
			"doctype": "JK Retention Entry",
			"company": self.company,
			"project": self.project,
			"customer": self.customer,
			"retention_amount": amount,
			"release_due_date": due_date,
			"status": "Pending",
			"remarks": TEST_MARK,
		})
		entry.insert(ignore_permissions=True)
		entry.submit()
		return entry

	# ---------------------------------------------------------------- schema
	def test_doctype_is_submittable(self):
		self.assertTrue(frappe.get_meta("JK Retention Entry").is_submittable)

	def test_status_options_cover_the_retention_lifecycle(self):
		options = frappe.get_meta("JK Retention Entry").get_field("status").options.split("\n")
		self.assertEqual(options, ["Pending", "Due", "Released", "Cancelled"])

	def test_release_fields_exist_for_the_unbuilt_release_flow(self):
		# BRD-18 release is not implemented yet; the fields it will use must exist.
		meta = frappe.get_meta("JK Retention Entry")
		self.assertTrue(meta.get_field("release_invoice"))
		self.assertTrue(meta.get_field("payment_entry"))

	# ------------------------------------------------------------- behaviour
	def test_entry_can_be_submitted_and_cancelled(self):
		entry = self._entry(add_days(nowdate(), 365), amount=9027.5)
		self.assertEqual(entry.docstatus, 1)
		self.assertEqual(entry.status, "Pending")
		entry.cancel()
		self.assertEqual(entry.docstatus, 2)

	def test_daily_task_promotes_retention_past_its_release_date(self):
		"""BRD-18: the daily job is what moves Pending -> Due."""
		entry = self._entry(add_days(nowdate(), -1))
		promoted = update_retention_status()
		self.assertIn(entry.name, promoted)
		self.assertEqual(
			frappe.db.get_value("JK Retention Entry", entry.name, "status"), "Due"
		)

	def test_future_dated_retention_is_left_pending(self):
		entry = self._entry(add_days(nowdate(), 30))
		self.assertNotIn(entry.name, update_retention_status())
		self.assertEqual(
			frappe.db.get_value("JK Retention Entry", entry.name, "status"), "Pending"
		)

	def test_daily_task_is_idempotent(self):
		# Running twice must not re-promote an entry already marked Due.
		entry = self._entry(add_days(nowdate(), -5))
		update_retention_status()
		self.assertNotIn(entry.name, update_retention_status())
