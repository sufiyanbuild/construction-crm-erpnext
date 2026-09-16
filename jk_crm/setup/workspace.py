"""BRD-25: the module needs a front door.

Without a Workspace the dashboard, the eight reports and the retention register
are only reachable by search, which is why they went unused on the demo site.
This is built after dashboards.py so the cards it references already exist.
"""

import json

import frappe

WORKSPACE = "JK CRM"

# Cards are named from their label by Number Card's autoname, so these are the
# names dashboards.py actually creates - not the spec keys.
CARDS = [
	"Open Tenders",
	"Estimations Pending",
	"Quotations Awaiting Approval",
	"Ongoing Projects",
	"Overdue Invoices",
	"Total Receivable",
]

CHART = "JK Invoice Status Mix"

SHORTCUTS = [
	{"label": "Opportunity", "type": "DocType", "link_to": "Opportunity"},
	{"label": "Quotation", "type": "DocType", "link_to": "Quotation"},
	{"label": "Project", "type": "DocType", "link_to": "Project"},
	{"label": "Sales Invoice", "type": "DocType", "link_to": "Sales Invoice"},
	{"label": "JK Retention Entry", "type": "DocType", "link_to": "JK Retention Entry"},
	{"label": "JK CRM Settings", "type": "DocType", "link_to": "JK CRM Settings"},
]

# Card Break rows open a group; Link rows fill it. Mirrors how the stock
# Projects and Selling workspaces are structured.
LINKS = [
	("Card Break", "Sales & Tendering", None, None),
	("Link", "Lead", "DocType", "Lead"),
	("Link", "Opportunity", "DocType", "Opportunity"),
	("Link", "Quotation", "DocType", "Quotation"),
	("Link", "Sales Order", "DocType", "Sales Order"),

	("Card Break", "Projects", None, None),
	("Link", "Project", "DocType", "Project"),
	("Link", "Task", "DocType", "Task"),
	("Link", "Purchase Order", "DocType", "Purchase Order"),
	("Link", "Delivery Note", "DocType", "Delivery Note"),

	("Card Break", "Billing & Retention", None, None),
	("Link", "Sales Invoice", "DocType", "Sales Invoice"),
	("Link", "Payment Entry", "DocType", "Payment Entry"),
	("Link", "JK Retention Entry", "DocType", "JK Retention Entry"),

	("Card Break", "Reports", None, None),
	("Link", "JK Bid and Tender Deadline Report", "Report", "JK Bid and Tender Deadline Report"),
	("Link", "JK Estimation Workload Report", "Report", "JK Estimation Workload Report"),
	("Link", "JK Pending Approval Report", "Report", "JK Pending Approval Report"),
	("Link", "JK Invoice Status Report", "Report", "JK Invoice Status Report"),
	("Link", "JK Retention Report", "Report", "JK Retention Report"),
	("Link", "JK Variation Order Report", "Report", "JK Variation Order Report"),
	("Link", "JK Warranty and Guarantee Report", "Report", "JK Warranty and Guarantee Report"),
	("Link", "JK Project Commercial Summary", "Report", "JK Project Commercial Summary"),

	("Card Break", "Configuration", None, None),
	("Link", "JK CRM Settings", "DocType", "JK CRM Settings"),
]


def _content(cards, chart):
	"""Workspace body: number cards first, then the chart, then the link cards."""
	blocks = [{"id": "jkspacer", "type": "spacer", "data": {"col": 12}}]
	for idx, card in enumerate(cards):
		blocks.append({
			"id": f"jkcard{idx}", "type": "number_card",
			"data": {"number_card_name": card, "col": 4},
		})
	if chart:
		blocks.append({
			"id": "jkchart", "type": "chart",
			"data": {"chart_name": chart, "col": 12},
		})
	blocks.append({
		"id": "jkhead", "type": "header",
		"data": {"text": "<span class=\"h4\"><b>Documents &amp; Reports</b></span>", "col": 12},
	})
	for label in ["Sales & Tendering", "Projects", "Billing & Retention", "Reports", "Configuration"]:
		blocks.append({
			"id": f"jkc{abs(hash(label)) % 10**6}", "type": "card",
			"data": {"card_name": label, "col": 4},
		})
	return json.dumps(blocks)


def execute():
	# Only reference cards and charts that were actually created on this site,
	# otherwise the workspace renders broken tiles.
	cards = [c for c in CARDS if frappe.db.exists("Number Card", c)]
	chart = CHART if frappe.db.exists("Dashboard Chart", CHART) else None
	missing = set(CARDS) - set(cards)
	if missing:
		print(f"WARN: skipping number cards not present on this site: {sorted(missing)}")

	if frappe.db.exists("Workspace", WORKSPACE):
		frappe.delete_doc("Workspace", WORKSPACE, force=1, ignore_permissions=True)

	doc = frappe.get_doc({
		"doctype": "Workspace",
		"name": WORKSPACE,
		"label": WORKSPACE,
		"title": WORKSPACE,
		"module": "JK CRM",
		"app": "jk_crm",
		"icon": "crm",
		"indicator_color": "blue",
		"public": 1,
		"is_hidden": 0,
		"sequence_id": 12.0,
		"content": _content(cards, chart),
		"number_cards": [{"number_card_name": c, "label": c} for c in cards],
		"charts": ([{"chart_name": chart, "label": chart}] if chart else []),
		"shortcuts": [
			{"type": s["type"], "label": s["label"], "link_to": s["link_to"]}
			for s in SHORTCUTS
			if frappe.db.exists("DocType", s["link_to"])
		],
		"links": [
			{
				"type": t,
				"label": label,
				"link_type": link_type,
				"link_to": link_to,
				"onboard": 0,
				"is_query_report": 1 if link_type == "Report" else 0,
				"hidden": 0,
			}
			for (t, label, link_type, link_to) in LINKS
			if t == "Card Break"
			or (link_type == "DocType" and frappe.db.exists("DocType", link_to))
			or (link_type == "Report" and frappe.db.exists("Report", link_to))
		],
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	print(
		f"CREATED workspace: {WORKSPACE} "
		f"({len(cards)} cards, {1 if chart else 0} chart, {len(doc.links)} links, "
		f"{len(doc.shortcuts)} shortcuts)"
	)
