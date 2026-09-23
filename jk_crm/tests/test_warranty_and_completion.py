"""Warranty (BRD-23) and completion certificate (BRD-15) rules.

Warranty was explicitly called out for verification: fields existing is not the
same as the requirement being met. These tests pin the behaviour the BRD asks
for - dates derived from completion/handover, a status that ages, and a
certificate issued on completion.
"""

import unittest

import frappe
from frappe.utils import add_days, add_months, getdate, nowdate

from jk_crm.controllers import project_validate


def project(**fields):
	return frappe.get_doc({"doctype": "Project", "project_name": "Warranty Test", **fields})


class TestWarrantyRules(unittest.TestCase):
	def test_end_date_derived_from_start_and_period(self):
		doc = project(
			status="Open", jk_has_warranty=1,
			jk_warranty_start_date="2026-09-15", jk_warranty_period_months=24,
		)
		project_validate(doc)
		self.assertEqual(
			getdate(doc.jk_warranty_end_date), add_months(getdate("2026-09-15"), 24)
		)

	def test_start_date_defaults_from_completion_date(self):
		"""BRD-23 ties warranty to completion, so it should not need retyping."""
		doc = project(
			status="Open", jk_has_warranty=1,
			jk_completion_date="2026-06-01", jk_warranty_period_months=12,
		)
		project_validate(doc)
		self.assertEqual(getdate(doc.jk_warranty_start_date), getdate("2026-06-01"))
		self.assertEqual(
			getdate(doc.jk_warranty_end_date), add_months(getdate("2026-06-01"), 12)
		)

	def test_start_date_falls_back_to_handover_date(self):
		doc = project(
			status="Open", jk_has_warranty=1,
			jk_handover_date="2026-05-01", jk_warranty_period_months=6,
		)
		project_validate(doc)
		self.assertEqual(getdate(doc.jk_warranty_start_date), getdate("2026-05-01"))

	def test_missing_period_is_rejected(self):
		doc = project(status="Open", jk_has_warranty=1, jk_warranty_start_date="2026-09-15")
		with self.assertRaises(frappe.ValidationError):
			project_validate(doc)

	def test_missing_start_with_no_fallback_is_rejected(self):
		doc = project(status="Open", jk_has_warranty=1, jk_warranty_period_months=12)
		with self.assertRaises(frappe.ValidationError):
			project_validate(doc)

	def test_status_active_within_period(self):
		doc = project(
			status="Open", jk_has_warranty=1,
			jk_warranty_start_date=add_days(nowdate(), -30), jk_warranty_period_months=12,
		)
		project_validate(doc)
		self.assertEqual(doc.jk_warranty_status, "Active")

	def test_status_not_started_before_period(self):
		doc = project(
			status="Open", jk_has_warranty=1,
			jk_warranty_start_date=add_days(nowdate(), 30), jk_warranty_period_months=12,
		)
		project_validate(doc)
		self.assertEqual(doc.jk_warranty_status, "Not Started")

	def test_status_expired_after_period(self):
		doc = project(
			status="Open", jk_has_warranty=1,
			jk_warranty_start_date=add_months(getdate(nowdate()), -24),
			jk_warranty_period_months=12,
		)
		project_validate(doc)
		self.assertEqual(doc.jk_warranty_status, "Expired")

	def test_no_warranty_clears_dates_and_status(self):
		doc = project(
			status="Open", jk_has_warranty=0,
			jk_warranty_end_date="2030-01-01", jk_warranty_status="Active",
		)
		project_validate(doc)
		self.assertIsNone(doc.jk_warranty_end_date)
		self.assertEqual(doc.jk_warranty_status, "Not Applicable")


class TestCompletionCertificate(unittest.TestCase):
	def test_certificate_issued_on_completion(self):
		doc = project(status="Completed")
		project_validate(doc)
		self.assertTrue(doc.jk_completion_certificate_no)
		self.assertTrue(doc.jk_completion_certificate_no.startswith("JK-CC-"))
		self.assertEqual(getdate(doc.jk_completion_date), getdate(nowdate()))

	def test_no_certificate_while_project_is_open(self):
		doc = project(status="Open")
		project_validate(doc)
		self.assertFalse(doc.get("jk_completion_certificate_no"))

	def test_existing_certificate_is_not_reissued(self):
		doc = project(status="Completed", jk_completion_certificate_no="JK-CC-2026-0001")
		project_validate(doc)
		self.assertEqual(doc.jk_completion_certificate_no, "JK-CC-2026-0001")

	def test_print_format_exists(self):
		self.assertTrue(
			frappe.db.exists("Print Format", "JK Project Completion Certificate")
		)


class TestProjectProgressConfiguration(unittest.TestCase):
	"""BRD-12 is satisfied by standard ERPNext; verify it is actually configured."""

	def test_construction_template_exists(self):
		self.assertTrue(frappe.db.exists("Project Template", "JK Construction Project"))

	def test_template_has_stages(self):
		tasks = frappe.get_all(
			"Project Template Task", filters={"parent": "JK Construction Project"}
		)
		self.assertGreaterEqual(len(tasks), 5)

	def test_progress_method_supports_task_driven_calculation(self):
		options = frappe.get_meta("Project").get_field("percent_complete_method").options
		self.assertIn("Task Completion", options)
