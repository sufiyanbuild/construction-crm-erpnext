"""Email lead capture (BRD-01).

Frappe already does the heavy lifting: an Email Account with incoming enabled
fetches mail, creates a Communication, threads replies and stores attachments.
We add only the piece it lacks - resolving the sender to an existing Lead,
Contact or Customer so a second enquiry under a new subject does not open a
duplicate Lead.

Runs on Communication.after_insert, which fires for inbound mail regardless of
whether the Email Account uses append_to.
"""

import frappe

from jk_crm.integrations.lead_capture import (
	CHANNEL_EMAIL,
	find_or_create_lead,
	link_communication,
)

# Never capture a lead from our own automated mail.
IGNORED_PREFIXES = ("noreply@", "no-reply@", "mailer-daemon@", "postmaster@")


def capture_from_communication(doc, method=None):
	"""Resolve inbound email to a CRM party, creating a Lead when unknown."""
	if not _is_inbound_email(doc):
		return

	sender = (doc.sender or "").strip().lower()
	if not sender or sender.startswith(IGNORED_PREFIXES):
		return

	if not _capture_enabled():
		return

	# Already threaded onto a real business document by Frappe - leave it alone.
	if doc.reference_doctype and doc.reference_doctype != "Communication":
		return

	try:
		doctype, name, created = find_or_create_lead(
			channel=CHANNEL_EMAIL,
			sender_name=doc.sender_full_name,
			email=sender,
			subject=doc.subject,
		)
		if doctype:
			link_communication(doc, doctype, name)
			if created:
				frappe.db.set_value(
					"Lead", name, "jk_source_detail", f"Email: {doc.subject or ''}"[:140]
				)
	except Exception:
		# An enquiry is worth less than the mail pipeline. Log and move on.
		frappe.log_error(
			title="jk_crm email lead capture failed",
			message=frappe.get_traceback(),
		)


def _is_inbound_email(doc):
	return (
		doc.doctype == "Communication"
		and doc.communication_type == "Communication"
		and doc.communication_medium == "Email"
		and doc.sent_or_received == "Received"
	)


def _capture_enabled():
	from jk_crm.utils import get_settings

	settings = get_settings()
	# Default on: a site that has configured inbound mail wants the leads.
	return bool(settings.get("capture_leads_from_email", 1)) if settings else True
