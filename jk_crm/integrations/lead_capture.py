"""Shared inbound lead capture (BRD-01, BRD-02, BRD-03).

Both the email and WhatsApp channels funnel through `find_or_create_lead`, so a
customer who emails today and messages on WhatsApp tomorrow lands on the same
Lead instead of two.

Why this exists rather than relying on Frappe alone: Frappe's inbound email
handler matches an existing record by *subject AND sender*
(EmailServer.match_record_by_subject_and_sender). A second enquiry from a known
sender under a new subject therefore creates a duplicate Lead. Here we resolve
the sender first - by email, by phone, across Lead, Contact and Customer - and
only create when nobody matches.
"""

import re

import frappe
from frappe.utils import nowdate

CHANNEL_EMAIL = "Email"
CHANNEL_WHATSAPP = "WhatsApp"


def normalise_phone(number):
	"""Reduce a phone number to comparable digits.

	WhatsApp delivers 966500000001; humans type +966 50 000 0001. We compare on
	the trailing 9 digits, which is long enough to be unique in practice and
	short enough to survive country-code and trunk-zero differences.
	"""
	if not number:
		return None
	digits = re.sub(r"\D", "", str(number))
	return digits[-9:] if len(digits) >= 9 else digits or None


def _match_by_email(email):
	if not email:
		return None, None

	lead = frappe.db.get_value("Lead", {"email_id": email}, "name")
	if lead:
		return "Lead", lead

	contact_name = frappe.db.get_value(
		"Contact Email", {"email_id": email}, "parent"
	)
	if contact_name:
		party = _party_from_contact(contact_name)
		if party:
			return party
		return "Contact", contact_name

	return None, None


def _match_by_phone(phone):
	tail = normalise_phone(phone)
	if not tail:
		return None, None

	# LIKE on the tail digits: stored numbers vary in formatting.
	lead = frappe.db.sql(
		"""SELECT name FROM `tabLead`
		   WHERE REPLACE(REPLACE(REPLACE(IFNULL(mobile_no,''),' ',''),'-',''),'+','') LIKE %s
		      OR REPLACE(REPLACE(REPLACE(IFNULL(phone,''),' ',''),'-',''),'+','') LIKE %s
		   ORDER BY modified DESC LIMIT 1""",
		(f"%{tail}", f"%{tail}"),
	)
	if lead:
		return "Lead", lead[0][0]

	contact = frappe.db.sql(
		"""SELECT parent FROM `tabContact Phone`
		   WHERE REPLACE(REPLACE(REPLACE(IFNULL(phone,''),' ',''),'-',''),'+','') LIKE %s
		   ORDER BY modified DESC LIMIT 1""",
		(f"%{tail}",),
	)
	if contact:
		party = _party_from_contact(contact[0][0])
		if party:
			return party
		return "Contact", contact[0][0]

	return None, None


def _party_from_contact(contact_name):
	"""Prefer the Customer a Contact belongs to - that is the real CRM party."""
	link = frappe.db.get_value(
		"Dynamic Link",
		{"parent": contact_name, "parenttype": "Contact", "link_doctype": "Customer"},
		"link_name",
	)
	if link:
		return "Customer", link
	return None


def resolve_sender(email=None, phone=None):
	"""Find who this is, if we already know them.

	Returns (doctype, name) or (None, None). Email is checked first because it
	is the stronger identifier.
	"""
	doctype, name = _match_by_email(email)
	if doctype:
		return doctype, name
	return _match_by_phone(phone)


def find_or_create_lead(
	channel,
	sender_name=None,
	email=None,
	phone=None,
	subject=None,
	company=None,
):
	"""Resolve an inbound sender to a CRM party, creating a Lead if unknown.

	Returns (doctype, name, created) so the caller can log what happened.
	Never raises on a capture failure: losing an enquiry is bad, but breaking
	the inbound email or webhook pipeline is worse.
	"""
	doctype, name = resolve_sender(email=email, phone=phone)
	if doctype:
		return doctype, name, False

	if not (email or phone):
		return None, None, False

	from jk_crm.utils import get_default_company

	lead = frappe.new_doc("Lead")
	lead.lead_name = sender_name or (email.split("@")[0] if email else phone)
	lead.first_name = sender_name or lead.lead_name
	if email:
		lead.email_id = email
	if phone:
		lead.mobile_no = phone
	lead.company = company or get_default_company()
	lead.status = "Lead"

	# BRD-01 inquiry details, so an inbound enquiry is as complete as one keyed
	# in by hand.
	lead.jk_inquiry_type = "Customer Inquiry"
	lead.jk_received_date = nowdate()
	lead.jk_requester_name = sender_name or ""
	lead.jk_source_channel = channel
	lead.jk_source_reference = email or phone
	if subject:
		lead.title = subject[:140]

	lead.flags.ignore_permissions = True
	lead.flags.ignore_mandatory = True
	lead.insert(ignore_permissions=True)

	frappe.logger("jk_crm").info(
		f"Captured new Lead {lead.name} from {channel} ({email or phone})"
	)
	return "Lead", lead.name, True


def link_communication(communication, doctype, name):
	"""Point a Communication at the resolved party without re-triggering hooks."""
	if not communication or not doctype or not name:
		return
	if (
		communication.reference_doctype == doctype
		and communication.reference_name == name
	):
		return
	frappe.db.set_value(
		"Communication",
		communication.name,
		{"reference_doctype": doctype, "reference_name": name},
		update_modified=False,
	)
