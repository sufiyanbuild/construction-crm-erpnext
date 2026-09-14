import json

import frappe

COMPANY = "JK Demo Contracting"

# BRD-25: operational visibility across leads, quotations, sales, projects,
# invoicing and overdue items.

NUMBER_CARDS = [
	{"name": "JK Open Tenders", "label": "Open Tenders",
	 "document_type": "Opportunity", "function": "Count",
	 "filters": [["Opportunity", "jk_is_tender", "=", 1, False],
				 ["Opportunity", "status", "in", ["Open", "Quotation"], False]]},
	{"name": "JK Estimations Pending", "label": "Estimations Pending",
	 "document_type": "Opportunity", "function": "Count",
	 "filters": [["Opportunity", "jk_estimation_status", "in", ["Not Started", "In Progress"], False]]},
	{"name": "JK Quotations Awaiting Approval", "label": "Quotations Awaiting Approval",
	 "document_type": "Quotation", "function": "Count",
	 "filters": [["Quotation", "workflow_state", "=", "Pending", False],
				 ["Quotation", "company", "=", COMPANY, False]]},
	{"name": "JK Ongoing Projects", "label": "Ongoing Projects",
	 "document_type": "Project", "function": "Count",
	 "filters": [["Project", "status", "=", "Open", False],
				 ["Project", "company", "=", COMPANY, False]]},
	{"name": "JK Overdue Invoices", "label": "Overdue Invoices",
	 "document_type": "Sales Invoice", "function": "Count",
	 "filters": [["Sales Invoice", "jk_invoice_status", "=", "Overdue", False],
				 ["Sales Invoice", "company", "=", COMPANY, False]]},
	{"name": "JK Total Receivable", "label": "Total Receivable",
	 "document_type": "Sales Invoice", "function": "Sum",
	 "aggregate_function_based_on": "outstanding_amount",
	 "filters": [["Sales Invoice", "docstatus", "=", 1, False],
				 ["Sales Invoice", "company", "=", COMPANY, False]]},
	{"name": "JK Retention Held", "label": "Retention Held",
	 "document_type": "JK Retention Entry", "function": "Sum",
	 "aggregate_function_based_on": "retention_amount",
	 "filters": [["JK Retention Entry", "docstatus", "=", 1, False],
				 ["JK Retention Entry", "status", "in", ["Pending", "Due"], False]]},
	{"name": "JK Variation Order Value", "label": "Variation Order Value",
	 "document_type": "Quotation", "function": "Sum",
	 "aggregate_function_based_on": "grand_total",
	 "filters": [["Quotation", "jk_is_variation_order", "=", 1, False],
				 ["Quotation", "docstatus", "=", 1, False]]},
]

CHARTS = [
	{"name": "JK Invoice Status Mix", "chart_name": "JK Invoice Status Mix",
	 "chart_type": "Group By", "group_by_type": "Count", "group_by_based_on": "jk_invoice_status",
	 "document_type": "Sales Invoice", "type": "Donut",
	 "filters": [["Sales Invoice", "docstatus", "=", 1, False],
				 ["Sales Invoice", "company", "=", COMPANY, False]]},
	{"name": "JK Billing by Type", "chart_name": "JK Billing by Type",
	 "chart_type": "Group By", "group_by_type": "Sum", "group_by_based_on": "jk_billing_type",
	 "aggregate_function_based_on": "grand_total",
	 "document_type": "Sales Invoice", "type": "Bar",
	 "filters": [["Sales Invoice", "docstatus", "=", 1, False],
				 ["Sales Invoice", "company", "=", COMPANY, False]]},
	{"name": "JK Procurement by Category", "chart_name": "JK Procurement by Category",
	 "chart_type": "Group By", "group_by_type": "Sum", "group_by_based_on": "jk_procurement_category",
	 "aggregate_function_based_on": "grand_total",
	 "document_type": "Purchase Order", "type": "Bar",
	 "filters": [["Purchase Order", "docstatus", "=", 1, False],
				 ["Purchase Order", "company", "=", COMPANY, False]]},
	{"name": "JK Estimation Status Mix", "chart_name": "JK Estimation Status Mix",
	 "chart_type": "Group By", "group_by_type": "Count", "group_by_based_on": "jk_estimation_status",
	 "document_type": "Opportunity", "type": "Pie",
	 "filters": [["Opportunity", "company", "=", COMPANY, False]]},
]

DASHBOARD = "JK CRM Management Dashboard"


def execute():
	card_names, chart_names = [], []
	for spec in NUMBER_CARDS:
		if frappe.db.exists("Number Card", spec["name"]):
			frappe.delete_doc("Number Card", spec["name"], force=1, ignore_permissions=True)
		doc = frappe.get_doc({
			"doctype": "Number Card", "name": spec["name"], "label": spec["label"],
			"type": "Document Type", "document_type": spec["document_type"],
			"function": spec["function"],
			"aggregate_function_based_on": spec.get("aggregate_function_based_on"),
			"filters_json": json.dumps(spec["filters"]),
			"is_public": 1, "show_percentage_stats": 0, "module": "JK CRM",
		})
		doc.insert(ignore_permissions=True)
		card_names.append(doc.name)   # autoname derives from label, not the key above
		print(f"CREATED number card: {doc.name}")

	for spec in CHARTS:
		if frappe.db.exists("Dashboard Chart", spec["name"]):
			frappe.delete_doc("Dashboard Chart", spec["name"], force=1, ignore_permissions=True)
		cdoc = frappe.get_doc({
			"doctype": "Dashboard Chart", "name": spec["name"],
			"chart_name": spec["chart_name"], "chart_type": spec["chart_type"],
			"document_type": spec["document_type"], "type": spec["type"],
			"group_by_type": spec.get("group_by_type"),
			"group_by_based_on": spec.get("group_by_based_on"),
			"aggregate_function_based_on": spec.get("aggregate_function_based_on"),
			"filters_json": json.dumps(spec["filters"]),
			"is_public": 1, "module": "JK CRM", "timeseries": 0,
		})
		cdoc.insert(ignore_permissions=True)
		chart_names.append(cdoc.name)
		print(f"CREATED chart: {cdoc.name}")

	if frappe.db.exists("Dashboard", DASHBOARD):
		frappe.delete_doc("Dashboard", DASHBOARD, force=1, ignore_permissions=True)
	frappe.get_doc({
		"doctype": "Dashboard", "dashboard_name": DASHBOARD, "is_default": 0,
		"module": "JK CRM",
		"cards": [{"card": n} for n in card_names],
		"charts": [{"chart": n} for n in chart_names],
	}).insert(ignore_permissions=True)
	frappe.db.commit()
	print(f"CREATED dashboard: {DASHBOARD} "
		  f"({len(card_names)} cards, {len(chart_names)} charts)")
