import frappe

# BRD-06: deadline alerts, pending approvals, expiring quotations, follow-ups.
# Channel is System Notification so the demo site needs no SMTP configuration;
# switching to Email on the client server is a one-field change.

NOTIFICATIONS = [
	{
		"name": "JK Bid Deadline Reminder",
		"subject": "Bid deadline approaching: {{ doc.name }}",
		"document_type": "Opportunity",
		"event": "Days Before",
		"date_changed": "jk_customer_bid_deadline",
		"days_in_advance": 2,
		"condition": "doc.jk_is_tender",
		"message": "Tender **{{ doc.jk_tender_ref_no or doc.name }}** for {{ doc.party_name }} "
				   "must be submitted by {{ doc.jk_customer_bid_deadline }}.",
		"recipients": [{"receiver_by_document_field": "jk_estimation_engineer"},
					   {"receiver_by_role": "JK Sales User"}],
	},
	{
		"name": "JK Estimation Deadline Reminder",
		"subject": "Internal estimation due: {{ doc.name }}",
		"document_type": "Opportunity",
		"event": "Days Before",
		"date_changed": "jk_internal_estimation_deadline",
		"days_in_advance": 1,
		"condition": "doc.jk_estimation_status != 'Completed'",
		"message": "The internal estimate for **{{ doc.name }}** is due {{ doc.jk_internal_estimation_deadline }} "
				   "and is still {{ doc.jk_estimation_status }}.",
		"recipients": [{"receiver_by_document_field": "jk_estimation_engineer"}],
	},
	{
		"name": "JK Quotation Expiry Reminder",
		"subject": "Quotation expiring: {{ doc.name }}",
		"document_type": "Quotation",
		"event": "Days Before",
		"date_changed": "valid_till",
		"days_in_advance": 3,
		"condition": "doc.docstatus == 1 and doc.status not in ('Ordered', 'Lost')",
		"message": "Quotation **{{ doc.name }}** for {{ doc.party_name }} expires on {{ doc.valid_till }}. "
				   "Follow up or request an extension.",
		"recipients": [{"receiver_by_role": "JK Sales User"}],
	},
	{
		"name": "JK Quotation Pending Approval",
		"subject": "Quotation awaiting your approval: {{ doc.name }}",
		"document_type": "Quotation",
		"event": "Value Change",
		"value_changed": "workflow_state",
		"condition": "doc.workflow_state == 'Pending'",
		"message": "Quotation **{{ doc.name }}** ({{ doc.currency }} {{ doc.grand_total }}) is pending approval.",
		"recipients": [{"receiver_by_role": "JK Management"}],
	},
	{
		"name": "JK Invoice Pending Approval",
		"subject": "Invoice awaiting your approval: {{ doc.name }}",
		"document_type": "Sales Invoice",
		"event": "Value Change",
		"value_changed": "workflow_state",
		"condition": "doc.workflow_state == 'Pending'",
		"message": "Sales Invoice **{{ doc.name }}** ({{ doc.currency }} {{ doc.grand_total }}) is pending approval.",
		"recipients": [{"receiver_by_role": "JK Management"}],
	},
	{
		"name": "JK Warranty Expiry Reminder",
		"subject": "Warranty expiring: {{ doc.name }}",
		"document_type": "Project",
		"event": "Days Before",
		"date_changed": "jk_warranty_end_date",
		"days_in_advance": 30,
		"condition": "doc.jk_has_warranty",
		"message": "Warranty for project **{{ doc.jk_project_code }} - {{ doc.project_name }}** "
				   "ends on {{ doc.jk_warranty_end_date }}.",
		"recipients": [{"receiver_by_document_field": "jk_project_manager"},
					   {"receiver_by_role": "JK Management"}],
	},
	{
		"name": "JK Retention Release Due",
		"subject": "Retention release due: {{ doc.name }}",
		"document_type": "JK Retention Entry",
		"event": "Days Before",
		"date_changed": "release_due_date",
		"days_in_advance": 7,
		"condition": "doc.status in ('Pending', 'Due')",
		"message": "Retention of {{ doc.retention_amount }} on project {{ doc.project }} "
				   "is due for release on {{ doc.release_due_date }}.",
		"recipients": [{"receiver_by_role": "JK Finance User"}],
	},
]


def execute():
	for spec in NOTIFICATIONS:
		if frappe.db.exists("Notification", spec["name"]):
			print(f"SKIP notification (exists): {spec['name']}")
			continue
		doc = frappe.get_doc({
			"doctype": "Notification",
			"name": spec["name"],
			"subject": spec["subject"],
			"document_type": spec["document_type"],
			"event": spec["event"],
			"channel": "System Notification",
			"enabled": 1,
			"is_standard": 0,
			"send_system_notification": 1,
			"message": spec["message"],
			"condition": spec.get("condition"),
			"date_changed": spec.get("date_changed"),
			"days_in_advance": spec.get("days_in_advance"),
			"value_changed": spec.get("value_changed"),
			"recipients": spec["recipients"],
		})
		doc.insert(ignore_permissions=True)
		print(f"CREATED notification: {spec['name']}")
	frappe.db.commit()
	print(f"Notifications complete: {len(NOTIFICATIONS)}.")


def create_opportunity_type():
	if not frappe.db.exists("Opportunity Type", "Tender"):
		frappe.get_doc({"doctype": "Opportunity Type", "name": "Tender",
			"description": "Tender / bid opportunity (BRD-01)"}).insert(ignore_permissions=True)
		frappe.db.commit()
		print("CREATED Opportunity Type: Tender")
