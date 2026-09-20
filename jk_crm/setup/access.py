"""Access and document-handling configuration (BRD-21, BRD-29).

Everything here is traceable to explicit BRD wording. Where the BRD is silent,
nothing is invented - the behaviour is left configurable and the open question
is recorded in JK CRM Settings and the final report.

BRD-21: "Allow users to attach and retain tender documents and project files
such as drawings, specifications, BOQ and other tender details against the
relevant lead/project." ERPNext ships Project with max_attachments = 4, which
cannot hold a drawing set plus specifications plus a BOQ. Raising that limit is
implementing the requirement, not inventing one.

BRD-29 / section 7: "Project users should access assigned projects and related
operational information." That is specific enough to implement, but switching it
on changes who can see what, so it ships OFF and is enabled per site once the
client confirms. See restrict_projects_to_assigned_users in JK CRM Settings.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

# BRD-21. ERPNext's stock value is 4 on Project; Lead, Opportunity and Quotation
# are already unlimited.
DOCUMENT_ATTACHMENT_LIMIT = 50

ATTACHMENT_DOCTYPES = ("Project", "Opportunity", "Lead", "Quotation")


def configure_document_storage():
	"""BRD-21: make the attachment limits fit construction document sets."""
	for doctype in ATTACHMENT_DOCTYPES:
		current = frappe.get_meta(doctype).get("max_attachments")
		# 0/None already means unlimited - leave those alone.
		if current and current < DOCUMENT_ATTACHMENT_LIMIT:
			make_property_setter(
				doctype, None, "max_attachments", DOCUMENT_ATTACHMENT_LIMIT, "Int",
				for_doctype=True, validate_fields_for_doctype=False,
			)
			print(f"Attachment limit raised on {doctype}: {current} -> {DOCUMENT_ATTACHMENT_LIMIT}")
	frappe.db.commit()


def execute():
	configure_document_storage()
	print("Access and document configuration complete (BRD-21).")


# ---------------------------------------------------------------- BRD-29
# Registered in hooks as permission_query_conditions. Returns no condition at
# all unless the site has explicitly opted in, so the default behaviour is
# unchanged from what the client has already seen.

PROJECT_ROLES = ("JK Project Manager", "JK Site Supervisor")


def project_permission_query(user=None):
	"""Restrict project users to their assigned projects, when enabled.

	BRD section 7 says project users "should access assigned projects". Assigned
	is taken from the two fields the BRD itself defines - Project Manager and
	Site Supervisor - and nothing else is inferred.

	Returns an empty string (no restriction) when the setting is off, when the
	user holds a role that needs full visibility, or when the user is an
	administrator - otherwise management reports and finance would break.
	"""
	from jk_crm.utils import get_setting

	if not get_setting("restrict_projects_to_assigned_users", default=0):
		return ""

	user = user or frappe.session.user
	if user in ("Administrator", "Guest"):
		return ""

	roles = set(frappe.get_roles(user))
	# Anyone who must see the whole portfolio is exempt.
	if roles & {"System Manager", "JK Management", "JK Finance User", "JK Sales User"}:
		return ""
	if not (roles & set(PROJECT_ROLES)):
		return ""

	safe_user = frappe.db.escape(user)
	return (
		f"(`tabProject`.`jk_project_manager` = {safe_user} "
		f"OR `tabProject`.`jk_site_supervisor` = {safe_user})"
	)


def project_has_permission(doc, ptype="read", user=None):
	"""Row-level counterpart to project_permission_query."""
	from jk_crm.utils import get_setting

	if not get_setting("restrict_projects_to_assigned_users", default=0):
		return True

	user = user or frappe.session.user
	if user in ("Administrator", "Guest"):
		return True

	roles = set(frappe.get_roles(user))
	if roles & {"System Manager", "JK Management", "JK Finance User", "JK Sales User"}:
		return True
	if not (roles & set(PROJECT_ROLES)):
		return True

	return user in (doc.get("jk_project_manager"), doc.get("jk_site_supervisor"))
