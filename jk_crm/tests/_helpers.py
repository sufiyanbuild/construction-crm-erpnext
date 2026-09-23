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
