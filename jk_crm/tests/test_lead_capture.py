"""Inbound lead capture tests (BRD-01, email + WhatsApp).

Covers the dedup logic that is the whole reason this layer exists: Frappe
matches inbound mail on subject AND sender, so without us a known sender under
a new subject opens a duplicate Lead.
"""

import unittest

import frappe

from jk_crm.integrations.lead_capture import (
	CHANNEL_EMAIL,
	CHANNEL_WHATSAPP,
	find_or_create_lead,
	normalise_phone,
	resolve_sender,
)

MARK = "jk_crm capture test"


class TestPhoneNormalisation(unittest.TestCase):
	"""WhatsApp and humans write the same number very differently."""

	def test_strips_formatting(self):
		self.assertEqual(normalise_phone("+966 50 000 0001"), "500000001")

	def test_matches_across_country_code_formats(self):
		self.assertEqual(normalise_phone("966500000001"), normalise_phone("+966-50-000-0001"))

	def test_handles_empty(self):
		self.assertIsNone(normalise_phone(None))
		self.assertIsNone(normalise_phone(""))

	def test_short_number_is_not_padded(self):
		self.assertEqual(normalise_phone("12345"), "12345")


class TestLeadCapture(unittest.TestCase):
	"""find_or_create_lead must never create a second Lead for a known sender."""

	def setUp(self):
		self.created = []

	def tearDown(self):
		for name in frappe.get_all(
			"Lead", filters={"jk_source_reference": ["like", "%captest%"]}, pluck="name"
		):
			frappe.delete_doc("Lead", name, force=1, ignore_permissions=True)
		for name in self.created:
			if frappe.db.exists("Lead", name):
				frappe.delete_doc("Lead", name, force=1, ignore_permissions=True)
		frappe.db.commit()

	def test_unknown_email_creates_lead(self):
		doctype, name, created = find_or_create_lead(
			channel=CHANNEL_EMAIL,
			sender_name="Captest One",
			email="one@captest.invalid",
			subject="Enquiry for fire pumps",
		)
		self.created.append(name)
		self.assertEqual(doctype, "Lead")
		self.assertTrue(created)
		lead = frappe.get_doc("Lead", name)
		self.assertEqual(lead.email_id, "one@captest.invalid")
		self.assertEqual(lead.jk_source_channel, CHANNEL_EMAIL)
		self.assertEqual(lead.jk_inquiry_type, "Customer Inquiry")

	def test_known_email_does_not_create_duplicate(self):
		"""The core requirement: second enquiry, different subject, same Lead."""
		_, first, created_first = find_or_create_lead(
			channel=CHANNEL_EMAIL, sender_name="Captest Two",
			email="two@captest.invalid", subject="First enquiry",
		)
		self.created.append(first)
		self.assertTrue(created_first)

		doctype, second, created_second = find_or_create_lead(
			channel=CHANNEL_EMAIL, sender_name="Captest Two",
			email="two@captest.invalid", subject="A completely different subject",
		)
		self.assertEqual(doctype, "Lead")
		self.assertEqual(second, first)
		self.assertFalse(created_second)

	def test_unknown_phone_creates_lead(self):
		doctype, name, created = find_or_create_lead(
			channel=CHANNEL_WHATSAPP, sender_name="Captest Three",
			phone="966500999001", subject="WhatsApp enquiry",
		)
		self.created.append(name)
		self.assertEqual(doctype, "Lead")
		self.assertTrue(created)
		self.assertEqual(frappe.db.get_value("Lead", name, "jk_source_channel"), CHANNEL_WHATSAPP)

	def test_same_person_across_channels_resolves_to_one_lead(self):
		"""Email today, WhatsApp tomorrow - still one Lead."""
		_, first, _ = find_or_create_lead(
			channel=CHANNEL_EMAIL, sender_name="Captest Four",
			email="four@captest.invalid", phone="966500999004",
		)
		self.created.append(first)

		doctype, second, created = find_or_create_lead(
			channel=CHANNEL_WHATSAPP, sender_name="Captest Four", phone="+966 50 099 9004",
		)
		self.assertEqual(second, first)
		self.assertFalse(created)

	def test_phone_match_tolerates_formatting(self):
		_, name, _ = find_or_create_lead(
			channel=CHANNEL_WHATSAPP, sender_name="Captest Five", phone="966500999005",
		)
		self.created.append(name)
		doctype, found = resolve_sender(phone="+966-50-099-9005")
		self.assertEqual(found, name)

	def test_no_identifier_creates_nothing(self):
		doctype, name, created = find_or_create_lead(channel=CHANNEL_EMAIL, sender_name="Nobody")
		self.assertIsNone(doctype)
		self.assertFalse(created)


class TestWhatsAppIntegrationGuard(unittest.TestCase):
	"""The WhatsApp layer must be inert when frappe_whatsapp is absent."""

	def test_is_available_reflects_doctype_presence(self):
		from jk_crm.integrations import whatsapp_capture

		self.assertEqual(
			whatsapp_capture.is_available(),
			bool(frappe.db.exists("DocType", "WhatsApp Message")),
		)

	def test_status_explains_what_is_missing(self):
		from jk_crm.integrations import whatsapp_capture

		status = whatsapp_capture.integration_status()
		self.assertIn("message", status)
		if not whatsapp_capture.is_available():
			self.assertFalse(status["available"])
			self.assertIn("frappe_whatsapp", status["message"])
