"""BRD-36: one traceable chain from lead to closure, built as real documents."""

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, flt
from erpnext.controllers.accounts_controller import get_taxes_and_charges

COMPANY = "JK Demo Contracting"
ABBR = "JKD"
CUSTOMER = "Riyadh Development Authority (Demo)"
SUPPLIER = "Gulf Mechanical Supplies (Demo)"
TAX_TEMPLATE = f"KSA VAT 15% - {ABBR}"
PURCHASE_TAX_TEMPLATE = f"KSA Input VAT 15% - {ABBR}"
COST_CENTER = f"Main - {ABBR}"

BID_DEADLINE = "2026-09-05 16:00:00"
EST_DEADLINE = "2026-08-30 17:00:00"


def _fractional_uom():
	"""Progress billing needs an item UOM that allows fractional quantities."""
	if not frappe.db.exists("UOM", "Lot"):
		frappe.get_doc({"doctype": "UOM", "uom_name": "Lot",
			"must_be_whole_number": 0}).insert(ignore_permissions=True)
		print("CREATED UOM: Lot")
	for item in ("FP-INSTALL", "FP-SUBCON", "FP-VAR-TANK"):
		if frappe.db.get_value("Item", item, "stock_uom") != "Lot":
			frappe.db.set_value("Item", item, "stock_uom", "Lot")
			for row in frappe.get_all("UOM Conversion Detail",
					filters={"parent": item}, pluck="name"):
				frappe.delete_doc("UOM Conversion Detail", row, force=1, ignore_permissions=True)
			frappe.get_doc({"doctype": "UOM Conversion Detail", "parent": item,
				"parenttype": "Item", "parentfield": "uoms", "uom": "Lot",
				"conversion_factor": 1}).insert(ignore_permissions=True)
	frappe.db.commit()


# ------------------------------------------------- BRD-01 / BRD-03: the lead
def step_lead():
	existing = frappe.db.get_value("Lead", {"company_name": CUSTOMER}, "name")
	if existing:
		return existing
	lead = frappe.get_doc({
		"doctype": "Lead",
		"first_name": "Mansour",
		"last_name": "Al-Dossary",
		"company_name": CUSTOMER,
		"email_id": "m.aldossary@rda-demo.local",
		"mobile_no": "+966500000001",
		"status": "Lead",
		"company": COMPANY,
		"lead_owner": "sales.manager@jkdemo.local",      # BRD-03 representative
		"jk_inquiry_type": "Tender",                      # BRD-01
		"jk_received_date": "2026-08-10",
		"jk_tender_ref_no": "RDA/TND/2026/0442",
		"jk_requester_name": "Mansour Al-Dossary",
	})
	lead.insert(ignore_permissions=True)
	frappe.db.commit()
	print(f"[BRD-01] Lead: {lead.name}")
	return lead.name


# ------------------- BRD-01/04/05/21: tender registration with dual deadlines
def step_opportunity(lead_name):
	existing = frappe.db.get_value("Opportunity", {"jk_tender_ref_no": "RDA/TND/2026/0442"}, "name")
	if existing:
		return existing
	opp = frappe.get_doc({
		"doctype": "Opportunity",
		"opportunity_from": "Lead",
		"party_name": lead_name,
		"opportunity_type": "Tender",
		"company": COMPANY,
		"currency": "SAR",
		"transaction_date": "2026-08-12",
		"expected_closing": "2026-09-20",
		"jk_is_tender": 1,
		"jk_tender_ref_no": "RDA/TND/2026/0442",
		"jk_customer_bid_deadline": BID_DEADLINE,            # BRD-05 customer deadline
		"jk_internal_estimation_deadline": EST_DEADLINE,     # BRD-05 internal deadline
		"jk_estimation_engineer": "estimation.lead@jkdemo.local",  # BRD-04
		"jk_estimation_status": "Completed",
		"jk_requester_name": "Mansour Al-Dossary",
		"items": [
			{"item_code": "FP-PUMP-200", "qty": 2, "uom": "Nos", "rate": 48000},
			{"item_code": "FP-INSTALL", "qty": 1, "uom": "Lot", "rate": 95000},
			{"item_code": "FP-SUBCON", "qty": 1, "uom": "Lot", "rate": 62000},
		],
	})
	opp.insert(ignore_permissions=True)
	frappe.db.commit()
	print(f"[BRD-01/04/05] Opportunity (Tender): {opp.name} "
		  f"| customer deadline {BID_DEADLINE} | internal {EST_DEADLINE}")
	return opp.name


# ------------------------------- BRD-07 / BRD-33 / BRD-34: quotation + approval
def step_quotation(opp_name):
	existing = frappe.db.get_value("Quotation",
		{"opportunity": opp_name, "jk_is_variation_order": 0}, "name")
	if existing:
		return existing
	from erpnext.crm.doctype.opportunity.opportunity import make_quotation
	q = make_quotation(opp_name)
	q.transaction_date = "2026-09-01"
	q.valid_till = "2026-10-15"           # BRD-33: per-quotation validity
	q.taxes_and_charges = TAX_TEMPLATE
	q.customer_address = "RDA Finance Dept-Billing"
	q.shipping_address_name = "RDA Site - North Ring-Shipping"
	q.contact_person = "Mansour Al-Dossary-Riyadh Development Authority (Demo)"
	for row in q.items:
		row.rate = {"FP-PUMP-200": 48000, "FP-INSTALL": 95000, "FP-SUBCON": 62000}[row.item_code]
		row.cost_center = COST_CENTER
	q.flags.ignore_permissions = True
	q.insert(ignore_permissions=True)

	# BRD-34: the quotation is approved before it leaves the building.
	apply_workflow(q, "Submit for Approval")
	apply_workflow(q, "Approve")
	q.reload()
	frappe.db.commit()
	print(f"[BRD-07/33/34] Quotation: {q.name} | state={q.workflow_state} "
		  f"| docstatus={q.docstatus} | valid_till={q.valid_till} | total=SAR {q.grand_total}")
	return q.name


# --------------------------------------- BRD-08 / BRD-18: sales order + retention
def step_sales_order(quotation_name):
	existing = frappe.db.get_value("Sales Order",
		{"customer": CUSTOMER, "docstatus": 1}, "name")
	if existing:
		return existing
	from erpnext.selling.doctype.quotation.quotation import make_sales_order
	so = make_sales_order(quotation_name)
	so.transaction_date = "2026-09-10"
	so.delivery_date = "2026-12-15"
	so.po_no = "RDA-PO-2026-8871"          # customer PO, kept separate from project code
	so.po_date = "2026-09-08"
	so.jk_has_retention = 1                 # BRD-18
	so.jk_retention_percentage = 10
	so.jk_retention_period_days = 365
	for row in so.items:
		row.delivery_date = "2026-12-15"
		row.cost_center = COST_CENTER
		if row.item_code == "FP-PUMP-200":
			row.warehouse = f"Stores - {ABBR}"
	# BRD-17: the commercial milestones the invoices will follow.
	so.payment_schedule = []
	so.flags.ignore_permissions = True
	so.insert(ignore_permissions=True)
	so.submit()
	frappe.db.commit()
	print(f"[BRD-08/18] Sales Order: {so.name} | customer PO={so.po_no} "
		  f"| total=SAR {so.grand_total} | retention {so.jk_retention_percentage}% "
		  f"= SAR {so.jk_retention_amount}")
	return so.name


def _link_customer_to_lead(lead_name):
	"""ERPNext creates a Customer from the Lead at order stage. Pointing the
	existing master at the Lead makes it reuse that master instead of creating
	a duplicate (see quotation._make_customer)."""
	if frappe.db.get_value("Customer", CUSTOMER, "lead_name") != lead_name:
		frappe.db.set_value("Customer", CUSTOMER, "lead_name", lead_name)
		frappe.db.set_value("Lead", lead_name, "status", "Converted")
		frappe.db.commit()
		print(f"[BRD-02] Linked Customer {CUSTOMER} to Lead {lead_name}")


def run_part1():
	_fractional_uom()
	lead = step_lead()
	_link_customer_to_lead(lead)
	opp = step_opportunity(lead)
	quo = step_quotation(opp)
	so = step_sales_order(quo)
	return {"lead": lead, "opportunity": opp, "quotation": quo, "sales_order": so}


# ------------- BRD-09/10/11/12/20: project, code, PM, site address, handover
def step_project(so_name):
	existing = frappe.db.get_value("Project", {"sales_order": so_name}, "name")
	if existing:
		return existing
	so = frappe.get_doc("Sales Order", so_name)
	prj = frappe.get_doc({
		"doctype": "Project",
		"project_name": "RDA North Ring Fire Protection System",
		"status": "Open",
		"project_type": "External",
		"is_active": "Yes",
		"customer": so.customer,
		"company": COMPANY,
		"sales_order": so_name,
		"expected_start_date": "2026-09-12",
		"expected_end_date": "2026-12-20",
		"jk_project_code": "PRJ-RDA-0442",              # BRD-09, separate from PO number
		"jk_customer_po_no": so.po_no,                   # BRD-09
		"jk_customer_po_status": "Open",                 # BRD-32
		"jk_project_manager": "pm.one@jkdemo.local",     # BRD-10
		"jk_site_supervisor": "supervisor@jkdemo.local", # BRD-12
		"jk_site_address": "RDA Site - North Ring-Shipping",  # BRD-20 third address
		"jk_handover_from": "sales.manager@jkdemo.local",
		"jk_handover_to": "pm.one@jkdemo.local",
		"jk_handover_checklist": [                       # BRD-11
			{"activity": "Signed contract and customer PO handed to Projects",
			 "responsible": "sales.manager@jkdemo.local", "target_date": "2026-09-12", "completed": 0},
			{"activity": "Approved technical submittals and BOQ transferred",
			 "responsible": "estimation.lead@jkdemo.local", "target_date": "2026-09-13", "completed": 0},
			{"activity": "Site access and delivery address confirmed",
			 "responsible": "pm.one@jkdemo.local", "target_date": "2026-09-14", "completed": 0},
			{"activity": "Payment terms and retention briefed to Finance",
			 "responsible": "finance@jkdemo.local", "target_date": "2026-09-15", "completed": 0},
		],
	})
	prj.flags.ignore_permissions = True
	prj.insert(ignore_permissions=True)
	frappe.db.commit()
	print(f"[BRD-09/10/20] Project: {prj.name} | code={prj.jk_project_code} "
		  f"| customer PO={prj.jk_customer_po_no} | PM={prj.jk_project_manager}")

	# BRD-11: run the handover through the workflow, not by editing a field.
	prj.reload()
	apply_workflow(prj, "Initiate Handover")
	prj.reload()
	print(f"[BRD-11] Handover state -> {prj.jk_handover_status}")

	for row in prj.jk_handover_checklist:
		row.completed = 1
	prj.jk_handover_date = "2026-09-15"
	prj.flags.ignore_permissions = True
	prj.save(ignore_permissions=True)

	prj.reload()
	apply_workflow(prj, "Accept Handover")
	prj.reload()
	frappe.db.commit()
	print(f"[BRD-11] Handover state -> {prj.jk_handover_status} "
		  f"| {len(prj.jk_handover_checklist)}/{len(prj.jk_handover_checklist)} checklist items closed")
	return prj.name


# ------------------------------------------ BRD-14: project procurement (non-stock + stock)
def step_procurement(project_name):
	pos = []

	# Subcontracted works - a service, proving procurement is not stock-only.
	if not frappe.db.exists("Purchase Order", {"jk_project": project_name,
			"jk_procurement_category": "Subcontracting", "docstatus": 1}):
		po = frappe.get_doc({
			"doctype": "Purchase Order", "supplier": SUPPLIER, "company": COMPANY,
			"transaction_date": "2026-09-11", "schedule_date": "2026-10-10",
			"currency": "SAR", "jk_project": project_name,
			"jk_procurement_category": "Subcontracting",
			"taxes_and_charges": PURCHASE_TAX_TEMPLATE,
			"items": [{"item_code": "FP-SUBCON", "qty": 1, "uom": "Lot", "rate": 44000,
					   "schedule_date": "2026-10-10", "project": project_name,
					   "cost_center": COST_CENTER}],
		})
		po.flags.ignore_permissions = True
		po.insert(ignore_permissions=True)
		po.submit()
		pos.append(po.name)
		print(f"[BRD-14] Purchase Order (Subcontracting): {po.name} | SAR {po.grand_total}")

	# Materials - a stock item, received into inventory so it can be delivered.
	if not frappe.db.exists("Purchase Order", {"jk_project": project_name,
			"jk_procurement_category": "Material", "docstatus": 1}):
		po2 = frappe.get_doc({
			"doctype": "Purchase Order", "supplier": SUPPLIER, "company": COMPANY,
			"transaction_date": "2026-09-11", "schedule_date": "2026-10-05",
			"currency": "SAR", "jk_project": project_name,
			"jk_procurement_category": "Material",
			"taxes_and_charges": PURCHASE_TAX_TEMPLATE,
			"items": [{"item_code": "FP-PUMP-200", "qty": 2, "uom": "Nos", "rate": 38000,
					   "schedule_date": "2026-10-05", "warehouse": f"Stores - {ABBR}",
					   "project": project_name, "cost_center": COST_CENTER}],
		})
		po2.flags.ignore_permissions = True
		po2.insert(ignore_permissions=True)
		po2.submit()
		pos.append(po2.name)
		print(f"[BRD-14] Purchase Order (Material): {po2.name} | SAR {po2.grand_total}")

		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
		pr = make_purchase_receipt(po2.name)
		pr.posting_date = "2026-09-14"
		pr.set_posting_time = 1
		for row in pr.items:
			row.warehouse = f"Stores - {ABBR}"
			row.cost_center = COST_CENTER
		pr.flags.ignore_permissions = True
		pr.insert(ignore_permissions=True)
		pr.submit()
		print(f"[BRD-14] Purchase Receipt: {pr.name} | 2 x FP-PUMP-200 into Stores - {ABBR}")

	frappe.db.commit()
	return pos


# --------------------------------------------- BRD-15: delivery documentation
def step_delivery(so_name, project_name):
	existing = frappe.db.get_value("Delivery Note", {"project": project_name, "docstatus": 1}, "name")
	if existing:
		return existing
	from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
	dn = make_delivery_note(so_name)
	dn.posting_date = "2026-09-15"
	dn.set_posting_time = 1
	dn.project = project_name
	# Only the stock item is physically delivered; services are certified separately.
	dn.items = [row for row in dn.items
				if frappe.db.get_value("Item", row.item_code, "is_stock_item")]
	for idx, row in enumerate(dn.items, start=1):
		row.idx = idx
		row.warehouse = f"Stores - {ABBR}"
		row.cost_center = COST_CENTER
		row.project = project_name
	dn.flags.ignore_permissions = True
	dn.insert(ignore_permissions=True)
	dn.submit()
	frappe.db.commit()
	print(f"[BRD-15] Delivery Note: {dn.name} | {len(dn.items)} stock line(s) delivered")
	return dn.name


def run_part2(ctx):
	project = step_project(ctx["sales_order"])
	ctx["project"] = project
	ctx["purchase_orders"] = step_procurement(project)
	ctx["delivery_note"] = step_delivery(ctx["sales_order"], project)
	return ctx


def _so_detail(so_name, item_code):
	return frappe.db.get_value("Sales Order Item", {"parent": so_name, "item_code": item_code}, "name")


def _cash_account():
	return (frappe.db.get_value("Account", {"company": COMPANY, "account_type": "Cash", "is_group": 0}, "name")
			or frappe.db.get_value("Account", {"company": COMPANY, "account_type": "Bank", "is_group": 0}, "name"))


def _make_invoice(so_name, project, billing_type, posting_date, due_date, lines,
				  retention_pct=0, progress_pct=0):
	"""BRD-17: advance / progress / final invoices against the project."""
	existing = frappe.db.get_value("Sales Invoice",
		{"project": project, "jk_billing_type": billing_type, "docstatus": 1}, "name")
	if existing:
		return existing

	items = []
	for item_code, qty, rate in lines:
		row = {
			"item_code": item_code, "qty": qty, "rate": rate,
			"uom": frappe.db.get_value("Item", item_code, "stock_uom"),
			"sales_order": so_name, "so_detail": _so_detail(so_name, item_code),
			"cost_center": COST_CENTER, "project": project,
		}
		if frappe.db.get_value("Item", item_code, "is_stock_item"):
			row["warehouse"] = f"Stores - {ABBR}"
		items.append(row)

	si = frappe.get_doc({
		"doctype": "Sales Invoice",
		"customer": CUSTOMER,
		"company": COMPANY,
		"currency": "SAR",
		"posting_date": posting_date,
		"set_posting_time": 1,
		"due_date": due_date,
		"project": project,
		"po_no": "RDA-PO-2026-8871",
		"customer_address": "RDA Finance Dept-Billing",     # BRD-20 invoicing address
		"shipping_address_name": "RDA Site - North Ring-Shipping",
		"contact_person": "Mansour Al-Dossary-Riyadh Development Authority (Demo)",
		"taxes_and_charges": TAX_TEMPLATE,
		# Naming the template is not enough on a server-side insert - the tax
		# rows have to be pulled in explicitly or the invoice posts VAT-free.
		"taxes": get_taxes_and_charges("Sales Taxes and Charges Template", TAX_TEMPLATE),
		"jk_billing_type": billing_type,
		"jk_progress_percentage": progress_pct,
		"jk_retention_percentage": retention_pct,
		"items": items,
	})
	si.flags.ignore_permissions = True
	si.insert(ignore_permissions=True)

	# BRD-34: invoices are approved before they are issued.
	apply_workflow(si, "Submit for Approval")
	apply_workflow(si, "Approve")
	si.reload()
	frappe.db.commit()
	print(f"[BRD-17] {billing_type} Invoice: {si.name} | SAR {si.grand_total} "
		  f"| retention {retention_pct}% = SAR {si.jk_retention_amount} "
		  f"| status={si.jk_invoice_status} | ZATCA={si.jk_zatca_status}")
	return si.name


def _pay(invoice, posting_date, amount):
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
	if frappe.db.exists("Payment Entry Reference",
			{"reference_name": invoice, "docstatus": 1}):
		return None
	pe = get_payment_entry("Sales Invoice", invoice)
	pe.posting_date = posting_date
	pe.reference_no = f"TT-{invoice[-5:]}"
	pe.reference_date = posting_date
	pe.paid_to = _cash_account()
	pe.paid_amount = amount
	pe.received_amount = amount
	pe.references = [r for r in pe.references if r.reference_name == invoice]
	for r in pe.references:
		r.allocated_amount = amount
	pe.flags.ignore_permissions = True
	pe.insert(ignore_permissions=True)
	pe.submit()
	frappe.db.commit()
	status = frappe.db.get_value("Sales Invoice", invoice, "jk_invoice_status")
	outstanding = frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount")
	print(f"[BRD-19] Payment {pe.name}: SAR {amount} against {invoice} "
		  f"| outstanding SAR {outstanding} | invoice status -> {status}")
	return pe.name


def step_billing(so_name, project):
	inv = {}
	# 20% advance, no retention withheld on the advance.
	inv["advance"] = _make_invoice(so_name, project, "Advance", "2026-09-11", "2026-09-12",
		[("FP-INSTALL", 0.2, 95000), ("FP-SUBCON", 0.2, 62000)])
	# 50% progress, 10% retention withheld.
	inv["progress"] = _make_invoice(so_name, project, "Progress", "2026-09-13", "2026-09-14",
		[("FP-INSTALL", 0.5, 95000), ("FP-SUBCON", 0.5, 62000)],
		retention_pct=10, progress_pct=50)
	# 30% final incl. delivered equipment, 10% retention withheld.
	inv["final"] = _make_invoice(so_name, project, "Final", "2026-09-15", "2026-10-15",
		[("FP-INSTALL", 0.3, 95000), ("FP-SUBCON", 0.3, 62000), ("FP-PUMP-200", 2, 48000)],
		retention_pct=10)

	# BRD-19: advance paid in full; progress paid less the retention withheld.
	_pay(inv["advance"], "2026-09-12", 36110.00)
	_pay(inv["progress"], "2026-09-14", 81247.50)
	# The final invoice is deliberately left open to exercise receivables reporting.
	return inv


# ------------------------------------------------ BRD-13: variation order
def step_variation(project):
	existing = frappe.db.get_value("Quotation", {"jk_is_variation_order": 1}, "name")
	if existing:
		return existing
	q = frappe.get_doc({
		"doctype": "Quotation",
		"quotation_to": "Customer",
		"party_name": CUSTOMER,
		"company": COMPANY,
		"currency": "SAR",
		"transaction_date": "2026-09-15",
		"valid_till": "2026-10-30",
		"order_type": "Sales",
		"taxes_and_charges": TAX_TEMPLATE,
		"taxes": get_taxes_and_charges("Sales Taxes and Charges Template", TAX_TEMPLATE),
		"customer_address": "RDA Finance Dept-Billing",
		"jk_is_variation_order": 1,                  # BRD-13
		"jk_variation_project": project,
		"jk_variation_reason": "Client requested an additional 20 m3 water storage tank "
							   "after site survey; outside original BOQ scope.",
		"items": [{"item_code": "FP-VAR-TANK", "qty": 1, "uom": "Lot", "rate": 41000,
				   "cost_center": COST_CENTER}],
	})
	q.flags.ignore_permissions = True
	q.insert(ignore_permissions=True)
	apply_workflow(q, "Submit for Approval")
	apply_workflow(q, "Approve")
	q.reload()
	frappe.db.commit()
	print(f"[BRD-13] Variation Order Quotation: {q.name} | project={project} "
		  f"| SAR {q.grand_total} | state={q.workflow_state}")
	return q.name


# ----------------------------- BRD-23 warranty, BRD-32 PO closure, BRD-12 progress
def step_closure(project):
	prj = frappe.get_doc("Project", project)
	prj.percent_complete = 100
	prj.status = "Completed"
	prj.jk_has_warranty = 1                       # BRD-23
	prj.jk_warranty_start_date = "2026-09-15"
	prj.jk_warranty_period_months = 24
	prj.jk_warranty_terms = ("24 months on equipment and workmanship from handover. "
							 "Excludes consumables and damage from misuse.")
	prj.jk_customer_po_status = "Closed"          # BRD-32
	prj.flags.ignore_permissions = True
	prj.save(ignore_permissions=True)
	prj.reload()
	frappe.db.commit()
	print(f"[BRD-23/32] Project closed: {prj.name} | warranty {prj.jk_warranty_start_date} "
		  f"-> {prj.jk_warranty_end_date} ({prj.jk_warranty_period_months} months) "
		  f"| customer PO={prj.jk_customer_po_status} | status={prj.status}")
	return prj.name


def run_part3(ctx):
	ctx["invoices"] = step_billing(ctx["sales_order"], ctx["project"])
	ctx["variation"] = step_variation(ctx["project"])
	step_closure(ctx["project"])
	return ctx
