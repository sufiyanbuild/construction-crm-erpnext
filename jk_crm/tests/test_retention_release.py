"""Retention release tests (BRD-18).

Closes the loop that was previously one-directional: retention could be tracked
in but never released out.
"""

import unittest

import frappe
from frappe.utils import add_days, nowdate

from jk_crm.retention import create_release_invoice

MARK = "jk_crm release test"


class TestRetentionRelease(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.company = frappe.db.get_value("Company", {}, "name")
		cls.project = frappe.db.get_value("Project", {}, "name")
		cls.customer = frappe.db.get_value("Customer", {}, "name")
		cls.ready = bool(cls.company and cls.project and cls.customer)

	def tearDown(self):
		for name in frappe.get_all(
			"JK Retention Entry", filters={"remarks": MARK}, pluck="name"
		):
			entry = frappe.get_doc("JK Retention Entry", name)
			if entry.release_invoice and frappe.db.exists("Sales Invoice", entry.release_invoice):
				inv = frappe.get_doc("Sales Invoice", entry.release_invoice)
				if inv.docstatus == 1:
					inv.cancel()
				frappe.delete_doc("Sales Invoice", inv.name, force=1, ignore_permissions=True)
			if entry.docstatus == 1:
				entry.cancel()
			frappe.delete_doc("JK Retention Entry", name, force=1, ignore_permissions=True)
		frappe.db.commit()

	def _entry(self, status="Due", amount=5000, due=None):
		if not self.ready:
			self.skipTest("site has no Company/Project/Customer")
		entry = frappe.get_doc({
			"doctype": "JK Retention Entry",
			"company": self.company,
			"project": self.project,
			"customer": self.customer,
			"retention_amount": amount,
			"release_due_date": due or add_days(nowdate(), -1),
			"status": "Pending",
			"remarks": MARK,
		})
		entry.insert(ignore_permissions=True)
		entry.submit()
		if status != "Pending":
			entry.db_set("status", status)
		return entry

	def test_release_creates_draft_invoice_of_correct_type(self):
		entry = self._entry()
		invoice_name = create_release_invoice(entry.name)
		invoice = frappe.get_doc("Sales Invoice", invoice_name)

		self.assertEqual(invoice.docstatus, 0, "release invoice must be left as draft for approval")
		self.assertEqual(invoice.jk_billing_type, "Retention Release")
		self.assertEqual(invoice.customer, self.customer)

	def test_release_invoice_withholds_no_further_retention(self):
		entry = self._entry()
		invoice = frappe.get_doc("Sales Invoice", create_release_invoice(entry.name))
		self.assertEqual(invoice.jk_retention_amount or 0, 0)
		self.assertEqual(invoice.jk_retention_percentage or 0, 0)

	def test_release_links_back_to_the_entry(self):
		entry = self._entry()
		invoice_name = create_release_invoice(entry.name)
		entry.reload()
		self.assertEqual(entry.release_invoice, invoice_name)

	def test_pending_retention_can_also_be_released(self):
		entry = self._entry(status="Pending", due=add_days(nowdate(), 30))
		self.assertTrue(create_release_invoice(entry.name))

	def test_double_release_is_refused(self):
		entry = self._entry()
		create_release_invoice(entry.name)
		entry.reload()
		with self.assertRaises(frappe.ValidationError):
			create_release_invoice(entry.name)

	def test_already_released_is_refused(self):
		entry = self._entry()
		entry.db_set("status", "Released")
		with self.assertRaises(frappe.ValidationError):
			create_release_invoice(entry.name)

	def test_zero_amount_is_refused(self):
		entry = self._entry(amount=0)
		with self.assertRaises(frappe.ValidationError):
			create_release_invoice(entry.name)

	def test_unsubmitted_entry_is_refused(self):
		if not self.ready:
			self.skipTest("site has no Company/Project/Customer")
		entry = frappe.get_doc({
			"doctype": "JK Retention Entry",
			"company": self.company, "project": self.project, "customer": self.customer,
			"retention_amount": 1000, "release_due_date": nowdate(),
			"status": "Pending", "remarks": MARK,
		})
		entry.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			create_release_invoice(entry.name)

	def test_release_date_field_exists_for_the_flow(self):
		self.assertTrue(frappe.get_meta("JK Retention Entry").get_field("release_date"))
