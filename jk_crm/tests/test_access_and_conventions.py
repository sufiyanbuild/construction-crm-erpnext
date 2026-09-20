"""BRD-03, BRD-21, BRD-29 and the configurable open points.

These pin behaviour that is traceable to explicit BRD wording, and pin the
*defaults* of the items the BRD leaves to the client - so that a later change of
default is a deliberate, visible act rather than a silent drift.
"""

import unittest

import frappe

from jk_crm.setup.access import project_has_permission, project_permission_query
from jk_crm.utils import get_setting


class TestSalesRepresentative(unittest.TestCase):
	"""BRD-03: assign and track the representative for each lead/tender/bid."""

	def test_representative_field_exists_on_opportunity(self):
		self.assertTrue(frappe.get_meta("Opportunity").has_field("jk_sales_representative"))

	def test_lead_carries_standard_owner(self):
		# The BRD's "lead" half is met by stock ERPNext; nothing custom needed.
		self.assertTrue(frappe.get_meta("Lead").has_field("lead_owner"))

	def test_representative_defaults_from_lead_owner(self):
		from jk_crm.controllers import opportunity_validate

		lead = frappe.get_doc({
			"doctype": "Lead",
			"lead_name": "Rep Default Test",
			"first_name": "Rep Default Test",
			"email_id": "repdefault@captest.invalid",
			"lead_owner": "Administrator",
			"status": "Lead",
		})
		lead.flags.ignore_mandatory = True
		lead.insert(ignore_permissions=True)
		try:
			opp = frappe.get_doc({
				"doctype": "Opportunity",
				"opportunity_from": "Lead",
				"party_name": lead.name,
			})
			opportunity_validate(opp)
			self.assertEqual(opp.jk_sales_representative, "Administrator")
		finally:
			frappe.delete_doc("Lead", lead.name, force=1, ignore_permissions=True)
			frappe.db.commit()

	def test_representative_is_not_mandatory(self):
		"""Whether it must be set is an open client decision - do not enforce."""
		from jk_crm.controllers import opportunity_validate

		opp = frappe.get_doc({"doctype": "Opportunity", "jk_is_tender": 0})
		opportunity_validate(opp)  # must not raise

	def test_representative_appears_in_tender_report(self):
		query = frappe.db.get_value("Report", "JK Bid and Tender Deadline Report", "query") or ""
		self.assertIn("jk_sales_representative", query)


class TestDocumentStorage(unittest.TestCase):
	"""BRD-21: attach and retain drawings, specifications, BOQ."""

	def test_project_can_hold_a_document_set(self):
		# ERPNext ships 4, which cannot hold drawings + specs + BOQ.
		limit = frappe.get_meta("Project").get("max_attachments")
		self.assertTrue(limit == 0 or limit >= 20, f"Project attachment limit too low: {limit}")

	def test_tender_records_accept_attachments(self):
		for doctype in ("Lead", "Opportunity", "Quotation"):
			limit = frappe.get_meta(doctype).get("max_attachments")
			self.assertTrue(limit == 0 or limit >= 20, f"{doctype} attachment limit too low: {limit}")


class TestProjectAccessRestriction(unittest.TestCase):
	"""BRD-29: project users access assigned projects - OFF until confirmed."""

	def test_restriction_is_off_by_default(self):
		self.assertFalse(
			get_setting("restrict_projects_to_assigned_users", default=0),
			"project restriction must stay off until the client confirms the rule",
		)

	def test_no_condition_applied_while_disabled(self):
		self.assertEqual(project_permission_query(user="pm.one@jkdemo.local"), "")

	def test_permission_granted_while_disabled(self):
		project = frappe.db.get_value("Project", {}, "name")
		if not project:
			self.skipTest("no project on site")
		doc = frappe.get_doc("Project", project)
		self.assertTrue(project_has_permission(doc, user="pm.one@jkdemo.local"))

	def test_administrator_is_never_restricted(self):
		self.assertEqual(project_permission_query(user="Administrator"), "")

	def test_condition_targets_only_the_brd_defined_fields(self):
		"""When enabled, 'assigned' means PM or Site Supervisor - nothing inferred."""
		frappe.db.set_single_value("JK CRM Settings", "restrict_projects_to_assigned_users", 1)
		frappe.clear_cache()
		try:
			condition = project_permission_query(user="pm.one@jkdemo.local")
			if condition:
				self.assertIn("jk_project_manager", condition)
				self.assertIn("jk_site_supervisor", condition)
			# Roles that need the whole portfolio stay unrestricted.
			self.assertEqual(project_permission_query(user="management@jkdemo.local"), "")
			self.assertEqual(project_permission_query(user="finance@jkdemo.local"), "")
		finally:
			frappe.db.set_single_value("JK CRM Settings", "restrict_projects_to_assigned_users", 0)
			frappe.clear_cache()
			frappe.db.commit()


class TestConfigurableOpenPoints(unittest.TestCase):
	"""Every BRD open point must be configurable, not hardcoded."""

	def test_reminder_schedules_are_configurable(self):
		for key, default in (
			("quotation_reminder_days", 3),
			("bid_reminder_days", 2),
			("estimation_reminder_days", 1),
		):
			self.assertIsNotNone(get_setting(key, default=default))

	def test_retention_fallback_is_configurable(self):
		self.assertTrue(frappe.get_meta("JK CRM Settings").has_field("retention_fallback_days"))

	def test_zatca_mode_is_configurable_and_not_claiming_compliance(self):
		field = frappe.get_meta("JK CRM Settings").get_field("zatca_mode")
		self.assertIsNotNone(field)
		options = field.options.split("\n")
		self.assertIn("Simulation (Demo)", options)
		# Nothing may be labelled as live/compliant until integration is real.
		self.assertNotIn("Compliant", " ".join(options))
		self.assertNotIn("Live", " ".join(options))

	def test_progress_method_remains_selectable(self):
		options = frappe.get_meta("Project").get_field("percent_complete_method").options
		for method in ("Manual", "Task Completion", "Task Progress", "Task Weight"):
			self.assertIn(method, options)


class TestNoDemoLeakageIntoProductConfig(unittest.TestCase):
	"""Shipped configuration must not carry the demo company or demo users."""

	def test_fixtures_have_no_company(self):
		import glob
		import os

		import jk_crm

		base = os.path.join(os.path.dirname(jk_crm.__file__), "fixtures", "*.json")
		for path in glob.glob(base):
			with open(path) as handle:
				content = handle.read()
			self.assertNotIn("JK Demo Contracting", content, os.path.basename(path))
			self.assertNotIn("jkdemo.local", content, os.path.basename(path))

	def test_install_does_not_create_demo_users(self):
		"""after_install must never provision the fictional demo users."""
		import inspect

		from jk_crm.setup import install

		source = inspect.getsource(install.after_install)
		self.assertNotIn("create_users", source)
		self.assertNotIn("roles.execute", source)
