app_name = "jk_crm"
app_title = "JK CRM"
app_publisher = "JK Consultancies"
app_description = "ERPNext CRM and Project lifecycle for JK Consultancies BRD QN-2026-0010"
app_email = "hello@jkconsultations.sa"
app_license = "mit"

after_install = "jk_crm.setup.install.after_install"

# BRD business rules -------------------------------------------------------
doc_events = {
	"Opportunity": {
		"validate": "jk_crm.controllers.opportunity_validate",
	},
	"Quotation": {
		"validate": "jk_crm.controllers.quotation_validate",
	},
	"Sales Order": {
		"validate": "jk_crm.controllers.sales_order_validate",
	},
	"Project": {
		"validate": "jk_crm.controllers.project_validate",
	},
	"Sales Invoice": {
		"validate": "jk_crm.controllers.sales_invoice_validate",
		"on_submit": [
			"jk_crm.controllers.sales_invoice_on_submit",
			"jk_crm.retention.mark_released_from_invoice",
		],
		"on_cancel": [
			"jk_crm.controllers.sales_invoice_on_cancel",
			"jk_crm.retention.reopen_released_from_invoice",
		],
	},
	"Payment Entry": {
		"on_submit": [
			"jk_crm.controllers.payment_entry_on_submit",
			"jk_crm.retention.link_release_payment",
		],
		"on_cancel": [
			"jk_crm.controllers.payment_entry_on_cancel",
			"jk_crm.retention.link_release_payment",
		],
	},
	# Inbound lead capture (BRD-01). The WhatsApp handler is inert unless
	# frappe_whatsapp is installed - see jk_crm.integrations.whatsapp_capture.
	"Communication": {
		"after_insert": "jk_crm.integrations.email_capture.capture_from_communication",
	},
	"WhatsApp Message": {
		"after_insert": "jk_crm.integrations.whatsapp_capture.capture_from_whatsapp_message",
	},
}

scheduler_events = {
	"daily": [
		"jk_crm.tasks.daily",
	],
}

# Everything this implementation customises is exported here, so the whole
# configuration moves to the client server with the app (no UI-only changes).
fixtures = [
	{"dt": "Custom Field", "filters": [["fieldname", "like", "jk_%"]]},
	{"dt": "Role", "filters": [["role_name", "like", "JK %"]]},
	{"dt": "Workflow", "filters": [["name", "like", "JK %"]]},
	# These states/actions carry plain business names, so they are listed
	# explicitly rather than matched on a "JK " prefix.
	{"dt": "Workflow State", "filters": [["name", "in", [
		"Draft", "Pending", "Approved", "Rejected",
		"Not Started", "Pending Handover", "Handover Accepted"]]]},
	{"dt": "Workflow Action Master", "filters": [["name", "in", [
		"Submit for Approval", "Approve", "Reject",
		"Initiate Handover", "Accept Handover"]]]},
	{"dt": "Notification", "filters": [["name", "like", "JK %"]]},
	{"dt": "Opportunity Type", "filters": [["name", "in", ["Tender"]]]},
]

# Report, Number Card, Dashboard Chart, Dashboard and Workspace are deliberately
# NOT exported as fixtures. Each one embeds a company in its filters, so shipping
# them would carry this site's company to every client server and a migrate would
# keep restoring it. They are built per site instead, from JK CRM Settings, by
# jk_crm.setup.reports / dashboards / workspace during after_install.
