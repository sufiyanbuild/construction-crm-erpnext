"""WhatsApp lead capture (BRD-01, new client requirement).

Design: frappe_whatsapp (github.com/shridarpatil/frappe_whatsapp) owns the
WhatsApp infrastructure - the Meta webhook, the WhatsApp Account credentials,
templates, and the WhatsApp Message doctype that inbound messages land in. It
does NOT create Leads. That gap is what this module fills, and it is the only
part that belongs to us.

This module is inert until frappe_whatsapp is installed: the hook is registered
unconditionally but `is_available()` short-circuits when the doctype is absent,
so jk_crm installs and runs normally on a site with no WhatsApp at all.

External setup required before any of this does anything (see README):
  - a Meta WhatsApp Business account
  - Access Token, Phone Number ID, Business Account ID, App ID
  - a webhook verify token, with the `messages` field subscribed
No credential is stored in this app; they live in frappe_whatsapp's own
WhatsApp Account doctype on the server.
"""

import frappe

from jk_crm.integrations.lead_capture import (
	CHANNEL_WHATSAPP,
	find_or_create_lead,
	normalise_phone,
)

WHATSAPP_MESSAGE = "WhatsApp Message"


def is_available():
	"""True when frappe_whatsapp is installed on this site."""
	return bool(frappe.db.exists("DocType", WHATSAPP_MESSAGE))


def capture_from_whatsapp_message(doc, method=None):
	"""Resolve an inbound WhatsApp message to a CRM party.

	Creates a Lead for an unknown number and records the conversation against
	it, so follow-up and conversion to Opportunity work exactly as they do for
	a lead keyed in by hand.
	"""
	if not _is_inbound(doc):
		return

	if not _capture_enabled():
		return

	# frappe_whatsapp stores the sender in `from`, which is a Python keyword;
	# depending on version it is exposed as `from_` or only through get().
	phone = getattr(doc, "from_", None) or doc.get("from")
	if not phone:
		return

	try:
		doctype, name, created = find_or_create_lead(
			channel=CHANNEL_WHATSAPP,
			sender_name=doc.get("profile_name"),
			phone=str(phone),
			subject=(doc.get("message") or "")[:140],
		)
		if not doctype:
			return

		_link_message(doc, doctype, name)

		if created:
			frappe.db.set_value(
				"Lead",
				name,
				"jk_source_detail",
				f"WhatsApp: {(doc.get('message') or '')[:120]}",
			)

		# Keep the conversation readable inside the CRM, not only in the
		# WhatsApp Message list.
		_record_communication(doc, doctype, name, phone)
	except Exception:
		frappe.log_error(
			title="jk_crm WhatsApp lead capture failed",
			message=frappe.get_traceback(),
		)


def _is_inbound(doc):
	return doc.doctype == WHATSAPP_MESSAGE and (doc.get("type") or "").lower() == "incoming"


def _link_message(doc, doctype, name):
	"""Attach the WhatsApp Message to the party, if the app exposes the fields."""
	meta = frappe.get_meta(WHATSAPP_MESSAGE)
	updates = {}
	if meta.has_field("reference_doctype"):
		updates["reference_doctype"] = doctype
	if meta.has_field("reference_name"):
		updates["reference_name"] = name
	if updates:
		frappe.db.set_value(WHATSAPP_MESSAGE, doc.name, updates, update_modified=False)


def _record_communication(doc, doctype, name, phone):
	"""Mirror the message as a Communication so it shows in the party timeline."""
	message = doc.get("message")
	if not message:
		return
	comm = frappe.new_doc("Communication")
	comm.communication_type = "Communication"
	comm.communication_medium = "Chat"
	comm.sent_or_received = "Received"
	comm.subject = f"WhatsApp from {phone}"
	comm.content = message
	comm.reference_doctype = doctype
	comm.reference_name = name
	comm.phone_no = str(phone)
	comm.flags.ignore_permissions = True
	comm.insert(ignore_permissions=True)


def _capture_enabled():
	from jk_crm.utils import get_settings

	settings = get_settings()
	return bool(settings.get("capture_leads_from_whatsapp", 1)) if settings else True


def integration_status():
	"""Human-readable readiness, surfaced in JK CRM Settings and the report."""
	if not is_available():
		return {
			"available": False,
			"message": (
				"frappe_whatsapp is not installed. Install it and configure a "
				"WhatsApp Account with Meta credentials to enable WhatsApp lead capture."
			),
		}

	accounts = frappe.get_all("WhatsApp Account", limit=1)
	if not accounts:
		return {
			"available": True,
			"configured": False,
			"message": "frappe_whatsapp is installed but no WhatsApp Account is configured.",
		}

	return {
		"available": True,
		"configured": True,
		"message": "WhatsApp lead capture is active.",
	}
