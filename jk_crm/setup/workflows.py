import frappe

# BRD-11 handover control and BRD-34 approval control.

STATES = [
	("Draft", "Danger"), ("Pending", "Warning"), ("Approved", "Success"), ("Rejected", "Danger"),
	("Not Started", "Danger"), ("Pending Handover", "Warning"), ("Handover Accepted", "Success"),
]
ACTIONS = ["Submit for Approval", "Approve", "Reject", "Initiate Handover", "Accept Handover"]

WORKFLOWS = [
	{
		# BRD-34: quotations are approved before they reach the customer.
		"name": "JK Quotation Approval",
		"document_type": "Quotation",
		"workflow_state_field": "workflow_state",
		"is_active": 1,
		"send_email_alert": 0,
		"states": [
			{"state": "Draft", "doc_status": "0", "allow_edit": "JK Sales User"},
			{"state": "Pending", "doc_status": "0", "allow_edit": "JK Management"},
			{"state": "Approved", "doc_status": "1", "allow_edit": "JK Management"},
			{"state": "Rejected", "doc_status": "0", "allow_edit": "JK Sales User"},
		],
		"transitions": [
			{"state": "Draft", "action": "Submit for Approval", "next_state": "Pending", "allowed": "JK Sales User"},
			{"state": "Pending", "action": "Approve", "next_state": "Approved", "allowed": "JK Management"},
			{"state": "Pending", "action": "Reject", "next_state": "Rejected", "allowed": "JK Management"},
		],
	},
	{
		# BRD-34: invoices are approved by management before finance collects.
		"name": "JK Sales Invoice Approval",
		"document_type": "Sales Invoice",
		"workflow_state_field": "workflow_state",
		"is_active": 1,
		"send_email_alert": 0,
		"states": [
			{"state": "Draft", "doc_status": "0", "allow_edit": "JK Finance User"},
			{"state": "Pending", "doc_status": "0", "allow_edit": "JK Management"},
			{"state": "Approved", "doc_status": "1", "allow_edit": "JK Management"},
			{"state": "Rejected", "doc_status": "0", "allow_edit": "JK Finance User"},
		],
		"transitions": [
			{"state": "Draft", "action": "Submit for Approval", "next_state": "Pending", "allowed": "JK Finance User"},
			{"state": "Pending", "action": "Approve", "next_state": "Approved", "allowed": "JK Management"},
			{"state": "Pending", "action": "Reject", "next_state": "Rejected", "allowed": "JK Management"},
		],
	},
	{
		# BRD-11: the handover itself is the workflow, driven by our own field.
		"name": "JK Project Handover",
		"document_type": "Project",
		"workflow_state_field": "jk_handover_status",
		"is_active": 1,
		"send_email_alert": 0,
		"states": [
			{"state": "Not Started", "doc_status": "0", "allow_edit": "JK Sales User"},
			{"state": "Pending Handover", "doc_status": "0", "allow_edit": "JK Project Manager"},
			{"state": "Handover Accepted", "doc_status": "0", "allow_edit": "JK Project Manager"},
		],
		"transitions": [
			{"state": "Not Started", "action": "Initiate Handover", "next_state": "Pending Handover",
			 "allowed": "JK Sales User"},
			{"state": "Pending Handover", "action": "Accept Handover", "next_state": "Handover Accepted",
			 "allowed": "JK Project Manager"},
		],
	},
]


def execute():
	for state, style in STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state,
				"style": style}).insert(ignore_permissions=True)
	for action in ACTIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master",
				"workflow_action_name": action}).insert(ignore_permissions=True)
	frappe.db.commit()

	for wf in WORKFLOWS:
		if frappe.db.exists("Workflow", wf["name"]):
			print(f"SKIP workflow (exists): {wf['name']}")
			continue
		doc = frappe.get_doc({
			"doctype": "Workflow",
			"workflow_name": wf["name"],
			"document_type": wf["document_type"],
			"workflow_state_field": wf["workflow_state_field"],
			"is_active": wf["is_active"],
			"send_email_alert": wf["send_email_alert"],
			"states": [{"state": s["state"], "doc_status": s["doc_status"],
				"allow_edit": s["allow_edit"]} for s in wf["states"]],
			"transitions": [{"state": t["state"], "action": t["action"],
				"next_state": t["next_state"], "allowed": t["allowed"]} for t in wf["transitions"]],
		})
		doc.insert(ignore_permissions=True)
		print(f"CREATED workflow: {wf['name']} on {wf['document_type']}")
	frappe.db.commit()
	print("Workflows complete.")
