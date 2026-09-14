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
		"on_submit": "jk_crm.controllers.sales_invoice_on_submit",
		"on_cancel": "jk_crm.controllers.sales_invoice_on_cancel",
	},
	"Payment Entry": {
		"on_submit": "jk_crm.controllers.payment_entry_on_submit",
		"on_cancel": "jk_crm.controllers.payment_entry_on_cancel",
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
	{"dt": "Report", "filters": [["name", "like", "JK %"]]},
	{"dt": "Number Card", "filters": [["module", "=", "JK CRM"]]},
	{"dt": "Dashboard Chart", "filters": [["module", "=", "JK CRM"]]},
	{"dt": "Dashboard", "filters": [["module", "=", "JK CRM"]]},
	{"dt": "Opportunity Type", "filters": [["name", "in", ["Tender"]]]},
]
