"""Configuration applied on install.

Deliberately excludes company creation and demo data - those are demo-site only
and are run by hand (jk_crm.setup.demo_masters / demo_lifecycle).
"""

import frappe

from jk_crm.setup import custom_fields, dashboards, notifications, reports, roles, workflows


def after_install():
	custom_fields.execute()
	roles.create_roles()
	workflows.execute()
	notifications.execute()
	notifications.create_opportunity_type()
	reports.execute()
	dashboards.execute()
	frappe.db.commit()
	print("jk_crm configuration installed (BRD QN-2026-0010).")
