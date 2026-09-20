import frappe

from jk_crm.utils import get_default_company

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
	{
		"name": "JK Lead and Prospect Report",
		"ref_doctype": "Lead",
		"add_total_row": 0,
		"roles": ["JK Sales User", "JK Management", "System Manager"],
		"query": """
SELECT l.name                AS "Lead:Link/Lead:140",
       l.lead_name           AS "Lead Name:Data:180",
       l.company_name        AS "Organisation:Data:180",
       l.jk_inquiry_type     AS "Inquiry Type:Data:120",
       l.jk_source_channel   AS "Captured From:Data:110",
       l.jk_received_date    AS "Date Received:Date:110",
       l.jk_tender_ref_no    AS "Tender Ref:Data:130",
       l.lead_owner          AS "Representative:Link/User:170",
       l.status              AS "Status:Data:100",
       DATEDIFF(CURDATE(), DATE(l.modified)) AS "Days Since Activity:Int:150"
FROM `tabLead` l
WHERE IFNULL(l.company, %(company)s) = %(company)s
ORDER BY l.creation DESC
""",
	},
	{
		"name": "JK Quotation Expiry and Pending Report",
		"ref_doctype": "Quotation",
		"add_total_row": 1,
		"roles": ["JK Sales User", "JK Management", "System Manager"],
		"query": """
SELECT q.name              AS "Quotation:Link/Quotation:160",
       q.party_name        AS "Customer:Data:180",
       q.transaction_date  AS "Posting Date:Date:100",
       q.valid_till        AS "Valid Till:Date:100",
       DATEDIFF(q.valid_till, CURDATE()) AS "Days To Expiry:Int:120",
       q.grand_total       AS "Amount:Currency:140",
       q.workflow_state    AS "Approval:Data:110",
       q.status            AS "Status:Data:110"
FROM `tabQuotation` q
WHERE q.company = %(company)s
  AND q.docstatus < 2
  AND IFNULL(q.status, '') NOT IN ('Ordered', 'Lost')
ORDER BY q.valid_till IS NULL, q.valid_till ASC
""",
	},
	{
		"name": "JK Ongoing Project Report",
		"ref_doctype": "Project",
		"add_total_row": 0,
		"roles": ["JK Project Manager", "JK Site Supervisor", "JK Management", "JK Sales User", "System Manager"],
		"query": """
SELECT p.name                 AS "Project:Link/Project:150",
       p.jk_project_code      AS "Code:Data:110",
       p.project_name         AS "Project Name:Data:200",
       p.customer             AS "Customer:Link/Customer:170",
       p.jk_project_manager   AS "Project Manager:Link/User:160",
       p.jk_site_supervisor   AS "Site Supervisor:Link/User:160",
       p.jk_handover_status   AS "Handover:Data:130",
       p.status               AS "Status:Data:90",
       p.percent_complete     AS "Complete %%:Percent:100",
       p.expected_end_date    AS "Expected End:Date:110",
       DATEDIFF(p.expected_end_date, CURDATE()) AS "Days Remaining:Int:120"
FROM `tabProject` p
WHERE p.company = %(company)s AND p.status = 'Open'
ORDER BY p.expected_end_date IS NULL, p.expected_end_date ASC
""",
	},
	{
		"name": "JK Project Progress Report",
		"ref_doctype": "Project",
		"add_total_row": 0,
		"roles": ["JK Project Manager", "JK Site Supervisor", "JK Management", "System Manager"],
		"query": """
SELECT p.name                       AS "Project:Link/Project:150",
       p.jk_project_code            AS "Code:Data:100",
       p.project_name               AS "Project Name:Data:190",
       p.percent_complete_method    AS "Progress Method:Data:130",
       p.percent_complete           AS "Complete %%:Percent:100",
       COUNT(t.name)                AS "Total Tasks:Int:100",
       SUM(CASE WHEN t.status = 'Completed' THEN 1 ELSE 0 END) AS "Completed:Int:100",
       SUM(CASE WHEN t.status = 'Overdue' THEN 1 ELSE 0 END)   AS "Overdue Tasks:Int:120",
       SUM(CASE WHEN t.status IN ('Open','Working','Pending Review') THEN 1 ELSE 0 END) AS "Open Tasks:Int:100",
       p.jk_project_manager         AS "Project Manager:Link/User:160"
FROM `tabProject` p
LEFT JOIN `tabTask` t ON t.project = p.name
WHERE p.company = %(company)s AND p.status IN ('Open', 'Completed')
GROUP BY p.name
ORDER BY p.percent_complete ASC
""",
	},
	{
		"name": "JK Advance and Progress Billing Report",
		"ref_doctype": "Sales Invoice",
		"add_total_row": 1,
		"roles": ["JK Finance User", "JK Management", "JK Project Manager", "System Manager"],
		"query": """
SELECT si.project            AS "Project:Link/Project:150",
       p.jk_project_code     AS "Code:Data:100",
       si.name               AS "Invoice:Link/Sales Invoice:160",
       si.posting_date       AS "Posting Date:Date:100",
       si.jk_billing_type    AS "Billing Type:Data:120",
       si.jk_progress_percentage AS "Progress %%:Percent:100",
       si.grand_total        AS "Invoice Amount:Currency:140",
       si.jk_retention_amount AS "Retention Withheld:Currency:150",
       si.outstanding_amount AS "Outstanding:Currency:130",
       si.jk_invoice_status  AS "Status:Data:110"
FROM `tabSales Invoice` si
LEFT JOIN `tabProject` p ON p.name = si.project
WHERE si.company = %(company)s AND si.docstatus = 1
  AND si.jk_billing_type IN ('Advance', 'Progress', 'Final', 'Retention Release')
ORDER BY si.project, si.posting_date
""",
	},
	{
		"name": "JK Project Procurement Report",
		"ref_doctype": "Purchase Order",
		"add_total_row": 1,
		"roles": ["JK Procurement User", "JK Project Manager", "JK Management", "System Manager"],
		"query": """
SELECT po.jk_project              AS "Project:Link/Project:150",
       p.jk_project_code          AS "Code:Data:100",
       po.name                    AS "Purchase Order:Link/Purchase Order:160",
       po.supplier                AS "Supplier:Link/Supplier:180",
       po.transaction_date        AS "Posting Date:Date:100",
       po.jk_procurement_category AS "Category:Data:130",
       po.grand_total             AS "Order Value:Currency:140",
       po.status                  AS "Status:Data:110"
FROM `tabPurchase Order` po
LEFT JOIN `tabProject` p ON p.name = po.jk_project
WHERE po.company = %(company)s AND po.docstatus = 1
ORDER BY po.transaction_date DESC
""",
	},
	{
		"name": "JK Receivables and Overdue Report",
		"ref_doctype": "Sales Invoice",
		"add_total_row": 1,
		"roles": ["JK Finance User", "JK Management", "System Manager"],
		"query": """
SELECT si.customer            AS "Customer:Link/Customer:190",
       si.name                AS "Invoice:Link/Sales Invoice:160",
       si.project             AS "Project:Link/Project:140",
       si.posting_date        AS "Posting Date:Date:100",
       si.due_date            AS "Due Date:Date:100",
       DATEDIFF(CURDATE(), si.due_date) AS "Days Overdue:Int:110",
       si.grand_total         AS "Invoice Amount:Currency:140",
       si.outstanding_amount  AS "Outstanding:Currency:140",
       si.jk_invoice_status   AS "Status:Data:110"
FROM `tabSales Invoice` si
WHERE si.company = %(company)s AND si.docstatus = 1 AND si.outstanding_amount > 0
ORDER BY si.due_date ASC
""",
	},
	{
		"name": "JK Customer 360 Report",
		"ref_doctype": "Customer",
		"add_total_row": 1,
		"roles": ["JK Sales User", "JK Management", "JK Finance User", "System Manager"],
		"query": """
SELECT c.name AS "Customer:Link/Customer:200",
       (SELECT COUNT(*) FROM `tabOpportunity` o
         WHERE o.party_name = c.name AND o.company = %(company)s) AS "Opportunities:Int:120",
       (SELECT COUNT(*) FROM `tabQuotation` q
         WHERE q.party_name = c.name AND q.company = %(company)s AND q.docstatus = 1) AS "Quotations:Int:110",
       (SELECT COUNT(*) FROM `tabSales Order` so
         WHERE so.customer = c.name AND so.company = %(company)s AND so.docstatus = 1) AS "Orders:Int:90",
       (SELECT COUNT(*) FROM `tabProject` p
         WHERE p.customer = c.name AND p.company = %(company)s) AS "Projects:Int:90",
       (SELECT IFNULL(SUM(si.grand_total),0) FROM `tabSales Invoice` si
         WHERE si.customer = c.name AND si.company = %(company)s AND si.docstatus = 1) AS "Invoiced:Currency:140",
       (SELECT IFNULL(SUM(si.outstanding_amount),0) FROM `tabSales Invoice` si
         WHERE si.customer = c.name AND si.company = %(company)s AND si.docstatus = 1) AS "Outstanding:Currency:140",
       (SELECT IFNULL(SUM(r.retention_amount),0) FROM `tabJK Retention Entry` r
         WHERE r.customer = c.name AND r.docstatus = 1 AND r.status <> 'Released') AS "Retention Held:Currency:140",
       c.jk_cr_number AS "CR Number:Data:120"
FROM `tabCustomer` c
WHERE EXISTS (SELECT 1 FROM `tabSales Invoice` si WHERE si.customer = c.name AND si.company = %(company)s)
   OR EXISTS (SELECT 1 FROM `tabProject` p WHERE p.customer = c.name AND p.company = %(company)s)
   OR EXISTS (SELECT 1 FROM `tabOpportunity` o WHERE o.party_name = c.name AND o.company = %(company)s)
ORDER BY 7 DESC
""",
	},
]


def company_report_filter():
	"""Company filter for every JK query report.

	The default is resolved per site rather than shipped with the app. When no
	company is configured the filter simply opens empty and the user picks one -
	the filter stays mandatory either way, so no report can run unscoped.
	"""
	return {
		"fieldname": "company",
		"label": "Company",
		"fieldtype": "Link",
		"options": "Company",
		"mandatory": 1,
		"default": get_default_company() or "",
	}


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
			"filters": [company_report_filter()],
		}).insert(ignore_permissions=True)
		print(f"CREATED report: {spec['name']}")
	frappe.db.commit()
	print(f"Reports complete: {len(REPORTS)}.")
