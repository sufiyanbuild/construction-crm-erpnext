"""Shared test helpers.

Picking a Company and a Customer independently is unsafe on a bench that hosts
more than one project: the two can belong to different currencies, and ERPNext
then rejects the document with a party-account currency mismatch. These helpers
resolve a *consistent* set instead - the company the CRM is configured for, and
a customer that has actually transacted with it.
"""

import frappe


def crm_company():
	"""The company this CRM instance is configured for."""
	from jk_crm.utils import get_default_company

	return get_default_company()


def consistent_party(company=None):
	"""A (company, customer, project) set known to work together.

	Returns (None, None, None) when the site has no such set, so callers can
	skip rather than fail.
	"""
	company = company or crm_company()
	if not company:
		return None, None, None

	# A customer that already has a submitted invoice in this company is
	# guaranteed to have a compatible receivable account and currency.
	customer = frappe.db.get_value(
		"Sales Invoice", {"company": company, "docstatus": 1}, "customer"
	)
	if not customer:
		customer = frappe.db.get_value("Customer", {}, "name")

	project = frappe.db.get_value("Project", {"company": company}, "name")
	return company, customer, project


TEST_EMAIL_DOMAIN = "captest.invalid"
TEST_PHONE_PREFIX = "966500999"


def purge_capture_test_records():
	"""Delete everything the lead-capture tests create, including spillover.

	ERPNext creates a Contact from every Lead (Lead.after_insert), so deleting
	only the Lead leaves a Contact behind carrying the same email or phone. The
	next run then resolves that Contact instead of creating a Lead, and the test
	fails for a reason that has nothing to do with the code under test.
	"""
	import frappe

	# Contacts reachable by the test email domain or phone prefix.
	contacts = set()
	contacts.update(
		frappe.db.sql_list(
			"SELECT DISTINCT parent FROM `tabContact Email` WHERE email_id LIKE %s",
			(f"%{TEST_EMAIL_DOMAIN}",),
		)
	)
	contacts.update(
		frappe.db.sql_list(
			"SELECT DISTINCT parent FROM `tabContact Phone` WHERE phone LIKE %s",
			(f"{TEST_PHONE_PREFIX}%",),
		)
	)

	leads = set(
		frappe.db.sql_list(
			"SELECT name FROM `tabLead` WHERE email_id LIKE %s OR mobile_no LIKE %s",
			(f"%{TEST_EMAIL_DOMAIN}", f"{TEST_PHONE_PREFIX}%"),
		)
	)
	leads.update(
		frappe.db.sql_list(
			"SELECT name FROM `tabLead` WHERE jk_source_reference LIKE %s OR jk_source_reference LIKE %s",
			(f"%{TEST_EMAIL_DOMAIN}", f"{TEST_PHONE_PREFIX}%"),
		)
	)

	for name in leads:
		frappe.delete_doc("Lead", name, force=1, ignore_permissions=True)
	for name in contacts:
		if frappe.db.exists("Contact", name):
			frappe.delete_doc("Contact", name, force=1, ignore_permissions=True)

	frappe.db.commit()
	return {"leads": len(leads), "contacts": len(contacts)}
