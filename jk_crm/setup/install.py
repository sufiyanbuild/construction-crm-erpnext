"""Configuration applied on install.

Deliberately excludes company creation and demo data - those are demo-site only
and are run by hand (jk_crm.setup.demo_masters / demo_lifecycle).
"""

import frappe

from jk_crm.setup import (
	access,
	custom_fields,
	dashboards,
	notifications,
	print_formats,
	projects,
	reports,
	roles,
	workflows,
	workspace,
)


# Check fields added to an existing Single by a migration are written as 0
# before their declared default applies, which reads back as "switched off".
# Setting them explicitly on install keeps a fresh site behaving as documented.
SETTING_DEFAULTS = {
	"capture_leads_from_email": 1,
	"capture_leads_from_whatsapp": 1,
	"send_daily_digest": 1,
	"followup_idle_days": 7,
	"retention_fallback_days": 365,
	"quotation_reminder_days": 3,
	"bid_reminder_days": 2,
	"estimation_reminder_days": 1,
	"notification_channel": "System Notification",
	"zatca_mode": "Simulation (Demo)",
}


def ensure_settings_defaults():
	for fieldname, value in SETTING_DEFAULTS.items():
		if frappe.db.get_single_value("JK CRM Settings", fieldname) in (None, "", 0):
			frappe.db.set_single_value("JK CRM Settings", fieldname, value)
	frappe.db.commit()
	print("JK CRM Settings defaults applied.")


def after_install():
	ensure_settings_defaults()
	custom_fields.execute()
	roles.create_roles()
	workflows.execute()
	notifications.execute()
	notifications.create_opportunity_type()
	access.execute()
	projects.execute()
	print_formats.execute()
	reports.execute()
	dashboards.execute()
	workspace.execute()
	frappe.db.commit()
	print("jk_crm configuration installed (BRD QN-2026-0010).")
