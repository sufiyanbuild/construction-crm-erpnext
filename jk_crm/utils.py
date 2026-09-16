"""Shared helpers for jk_crm.

Everything site-specific is resolved here so that no report, card, chart or
notification carries a hardcoded company or channel. A fresh install starts with
JK CRM Settings empty; each helper degrades safely rather than guessing.
"""

import frappe

SETTINGS = "JK CRM Settings"

# Used only when the Sales Order carries no retention period and JK CRM Settings
# has not been filled in. Kept as the app's historical default so behaviour does
# not change silently; the real figure is a client decision (BRD-18).
DEFAULT_RETENTION_FALLBACK_DAYS = 365


def get_settings():
	"""The JK CRM Settings single, or None if the doctype is not yet migrated."""
	try:
		return frappe.get_cached_doc(SETTINGS)
	except Exception:
		return None


def get_default_company():
	"""Company for JK reports, cards and charts.

	Resolution order: JK CRM Settings, then Global Defaults, then the only
	company on the site. Returns None when the site has several companies and
	none has been nominated - callers must treat that as "do not filter by
	company" rather than inventing one.
	"""
	settings = get_settings()
	if settings and settings.get("default_company"):
		return settings.default_company

	global_default = frappe.defaults.get_global_default("company")
	if global_default:
		return global_default

	companies = frappe.get_all("Company", pluck="name", limit=2)
	if len(companies) == 1:
		return companies[0]

	return None


def get_notification_channel():
	"""Channel for the JK notifications.

	Email is only honoured when a default outgoing Email Account exists;
	otherwise Frappe would queue mail that can never be sent, so we fall back to
	System Notification and say so in the log.
	"""
	settings = get_settings()
	wanted = (settings.get("notification_channel") if settings else None) or "System Notification"

	if wanted == "Email" and not has_outgoing_email():
		frappe.logger("jk_crm").warning(
			"JK CRM Settings requests Email notifications but no default outgoing "
			"Email Account exists; falling back to System Notification."
		)
		return "System Notification"

	return wanted


def has_outgoing_email():
	"""True when the site can actually send mail."""
	return bool(
		frappe.db.exists("Email Account", {"enable_outgoing": 1, "default_outgoing": 1})
	)


def get_retention_fallback_days():
	"""Fallback retention period in days (BRD-18)."""
	settings = get_settings()
	if settings and settings.get("retention_fallback_days"):
		return int(settings.retention_fallback_days)
	return DEFAULT_RETENTION_FALLBACK_DAYS


def company_filter(doctype):
	"""A filters_json clause pinning `doctype` to the configured company.

	Returns an empty list when no company is configured, so a card or chart shows
	every company rather than silently reporting on the wrong one.
	"""
	company = get_default_company()
	if not company:
		return []
	return [[doctype, "company", "=", company, False]]
