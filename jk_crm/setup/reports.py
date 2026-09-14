import frappe

# BRD-26 / BRD-27: the reports ERPNext does not ship. Posting date AND deadline
# date appear together wherever the BRD asks for it (BRD-27).

ALL_ROLES = ["JK Management", "JK Sales User", "JK Estimation Engineer",
			 "JK Project Manager", "JK Finance User", "JK Procurement User", "System Manager"]

REPORTS = [
	{
		"name": "JK Bid and Tender Deadline Report",
		"ref_doctype": "Opportunity",
		"add_total_row": 0,
		"roles": ["JK Sales User", "JK Estimation Engineer", "JK Management", "System Manager"],
		"query": """
SELECT o.name                              AS "Opportunity:Link/Opportunity:150",
       o.jk_tender_ref_no                  AS "Tender Ref:Data:120",
       o.party_name                        AS "Customer:Data:180",
       o.transaction_date                  AS "Posting Date:Date:100",
       o.jk_customer_bid_deadline          AS "Customer Deadline:Datetime:160",
       o.jk_internal_estimation_deadline   AS "Internal Deadline:Datetime:160",
       DATEDIFF(o.jk_customer_bid_deadline, NOW()) AS "Days Left:Int:90",
       o.jk_estimation_engineer            AS "Estimation Engineer:Link/User:170",
       o.jk_estimation_status              AS "Estimation Status:Data:130",
       o.status                            AS "Opportunity Status:Data:130"
FROM `tabOpportunity` o
WHERE o.jk_is_tender = 1 AND o.company = %(company)s
ORDER BY o.jk_customer_bid_deadline ASC
""",
	},
	{
		"name": "JK Estimation Workload Report",
		"ref_doctype": "Opportunity",
		"add_total_row": 1,
		"roles": ["JK Estimation Engineer", "JK Management", "System Manager"],
		"query": """
SELECT o.jk_estimation_engineer AS "Estimation Engineer:Link/User:200",
       COUNT(*)                 AS "Total Assigned:Int:120",
       SUM(CASE WHEN o.jk_estimation_status = 'Not Started' THEN 1 ELSE 0 END) AS "Not Started:Int:110",
       SUM(CASE WHEN o.jk_estimation_status = 'In Progress' THEN 1 ELSE 0 END) AS "In Progress:Int:110",
       SUM(CASE WHEN o.jk_estimation_status = 'Completed'  THEN 1 ELSE 0 END) AS "Completed:Int:110",
       SUM(CASE WHEN o.jk_internal_estimation_deadline < NOW()
                 AND o.jk_estimation_status NOT IN ('Completed','Submitted') THEN 1 ELSE 0 END) AS "Overdue:Int:100"
FROM `tabOpportunity` o
WHERE IFNULL(o.jk_estimation_engineer, '') != '' AND o.company = %(company)s
GROUP BY o.jk_estimation_engineer
ORDER BY 6 DESC, 2 DESC
""",
	},
	{
		"name": "JK Pending Approval Report",
		"ref_doctype": "Quotation",
		"add_total_row": 0,
		"roles": ALL_ROLES,
		"query": """
SELECT 'Quotation' AS "Document Type:Data:130", q.name AS "Document:Data:170",
       q.party_name AS "Party:Data:190", q.grand_total AS "Amount:Currency:140",
       q.workflow_state AS "Workflow State:Data:130", q.modified AS "Waiting Since:Datetime:160"
FROM `tabQuotation` q WHERE q.workflow_state = 'Pending' AND q.company = %(company)s
UNION ALL
SELECT 'Sales Invoice', si.name, si.customer, si.grand_total, si.workflow_state, si.modified
FROM `tabSales Invoice` si WHERE si.workflow_state = 'Pending' AND si.company = %(company)s
UNION ALL
SELECT 'Project (Handover)', p.name, p.customer, 0, p.jk_handover_status, p.modified
FROM `tabProject` p WHERE p.jk_handover_status = 'Pending Handover' AND p.company = %(company)s
ORDER BY 6 ASC
""",
	},
	{
		"name": "JK Retention Report",
		"ref_doctype": "JK Retention Entry",
		"add_total_row": 1,
		"roles": ["JK Finance User", "JK Management", "JK Project Manager", "System Manager"],
		"query": """
SELECT r.name              AS "Retention Entry:Link/JK Retention Entry:170",
       r.project           AS "Project:Link/Project:150",
       p.jk_project_code   AS "Project Code:Data:110",
       r.customer          AS "Customer:Link/Customer:180",
       r.sales_invoice     AS "Source Invoice:Link/Sales Invoice:170",
       r.retention_amount  AS "Retention Amount:Currency:150",
       r.release_due_date  AS "Release Due:Date:110",
       DATEDIFF(r.release_due_date, CURDATE()) AS "Days To Release:Int:120",
       r.status            AS "Status:Data:100"
FROM `tabJK Retention Entry` r
LEFT JOIN `tabProject` p ON p.name = r.project
WHERE r.docstatus = 1 AND r.company = %(company)s
ORDER BY r.release_due_date ASC
""",
	},
	{
		"name": "JK Variation Order Report",
		"ref_doctype": "Quotation",
		"add_total_row": 1,
		"roles": ["JK Sales User", "JK Project Manager", "JK Management", "JK Finance User", "System Manager"],
		"query": """
SELECT q.name                 AS "Variation Quotation:Link/Quotation:180",
       q.jk_variation_project AS "Project:Link/Project:150",
       p.jk_project_code      AS "Project Code:Data:110",
       q.party_name           AS "Customer:Data:180",
       q.transaction_date     AS "Posting Date:Date:100",
       q.grand_total          AS "Variation Amount:Currency:150",
       q.jk_variation_reason  AS "Reason:Data:260",
       q.workflow_state       AS "Approval:Data:110",
       q.status               AS "Status:Data:100"
FROM `tabQuotation` q
LEFT JOIN `tabProject` p ON p.name = q.jk_variation_project
WHERE q.jk_is_variation_order = 1 AND q.company = %(company)s
ORDER BY q.transaction_date DESC
""",
	},
	{
		"name": "JK Warranty and Guarantee Report",
		"ref_doctype": "Project",
		"add_total_row": 0,
		"roles": ["JK Project Manager", "JK Management", "JK Site Supervisor", "System Manager"],
		"query": """
SELECT p.name                     AS "Project:Link/Project:160",
       p.jk_project_code          AS "Project Code:Data:110",
       p.project_name             AS "Project Name:Data:210",
       p.customer                 AS "Customer:Link/Customer:180",
       p.jk_warranty_start_date   AS "Warranty Start:Date:120",
       p.jk_warranty_period_months AS "Months:Int:80",
       p.jk_warranty_end_date     AS "Warranty End:Date:120",
       DATEDIFF(p.jk_warranty_end_date, CURDATE()) AS "Days Remaining:Int:120",
       p.jk_project_manager       AS "Project Manager:Link/User:170"
FROM `tabProject` p
WHERE p.jk_has_warranty = 1 AND p.company = %(company)s
ORDER BY p.jk_warranty_end_date ASC
""",
	},
	{
		"name": "JK Invoice Status Report",
		"ref_doctype": "Sales Invoice",
		"add_total_row": 1,
		"roles": ["JK Finance User", "JK Management", "System Manager"],
		"query": """
SELECT si.name               AS "Invoice:Link/Sales Invoice:170",
       si.posting_date       AS "Posting Date:Date:100",
       si.customer           AS "Customer:Link/Customer:180",
       si.project            AS "Project:Link/Project:150",
       si.jk_billing_type    AS "Billing Type:Data:120",
       si.grand_total        AS "Grand Total:Currency:140",
       si.outstanding_amount AS "Outstanding:Currency:140",
       si.due_date           AS "Due Date:Date:100",
       si.jk_invoice_status  AS "Invoice Status:Data:130",
       si.jk_zatca_status    AS "ZATCA Status:Data:140"
FROM `tabSales Invoice` si
WHERE si.docstatus < 2 AND si.company = %(company)s
ORDER BY si.posting_date DESC
""",
	},
	{
		"name": "JK Project Commercial Summary",
		"ref_doctype": "Project",
		"add_total_row": 1,
		"roles": ["JK Project Manager", "JK Finance User", "JK Management", "System Manager"],
		"query": """
SELECT p.name              AS "Project:Link/Project:160",
       p.jk_project_code   AS "Code:Data:100",
       p.project_name      AS "Project Name:Data:200",
       p.customer          AS "Customer:Link/Customer:170",
       p.jk_project_manager AS "Project Manager:Link/User:170",
       p.status            AS "Status:Data:100",
       p.percent_complete  AS "Percent Complete:Percent:130",
       IFNULL(so.ordered, 0)     AS "Order Value:Currency:140",
       IFNULL(si.invoiced, 0)    AS "Invoiced:Currency:130",
       IFNULL(si.outstanding, 0) AS "Outstanding:Currency:130",
       IFNULL(ret.retained, 0)   AS "Retention Held:Currency:140",
       IFNULL(po.purchased, 0)   AS "Procurement Cost:Currency:150"
FROM `tabProject` p
LEFT JOIN (SELECT project, SUM(grand_total) ordered FROM `tabSales Order`
           WHERE docstatus = 1 GROUP BY project) so ON so.project = p.name
LEFT JOIN (SELECT project, SUM(grand_total) invoiced, SUM(outstanding_amount) outstanding
           FROM `tabSales Invoice` WHERE docstatus = 1 GROUP BY project) si ON si.project = p.name
LEFT JOIN (SELECT project, SUM(retention_amount) retained FROM `tabJK Retention Entry`
           WHERE docstatus = 1 AND status != 'Released' GROUP BY project) ret ON ret.project = p.name
LEFT JOIN (SELECT jk_project, SUM(grand_total) purchased FROM `tabPurchase Order`
           WHERE docstatus = 1 GROUP BY jk_project) po ON po.jk_project = p.name
WHERE IFNULL(p.jk_project_code, '') != '' AND p.company = %(company)s
ORDER BY p.creation DESC
""",
	},
]


def execute():
	for spec in REPORTS:
		if frappe.db.exists("Report", spec["name"]):
			frappe.delete_doc("Report", spec["name"], force=1, ignore_permissions=True)
		frappe.get_doc({
			"doctype": "Report",
			"report_name": spec["name"],
			"ref_doctype": spec["ref_doctype"],
			"report_type": "Query Report",
			"module": "JK CRM",
			"is_standard": "No",
			"disabled": 0,
			"add_total_row": spec["add_total_row"],
			"query": spec["query"].strip(),
				"roles": [{"role": r} for r in spec["roles"] if frappe.db.exists("Role", r)],
			"filters": [{
				"fieldname": "company", "label": "Company", "fieldtype": "Link",
				"options": "Company", "mandatory": 1, "default": "JK Demo Contracting",
			}],
		}).insert(ignore_permissions=True)
		print(f"CREATED report: {spec['name']}")
	frappe.db.commit()
	print(f"Reports complete: {len(REPORTS)}.")
