import frappe

COMPANY = "JK Demo Contracting"
ABBR = "JKD"
CURRENCY = "SAR"
COUNTRY = "Saudi Arabia"
VAT_RATE = 15.0


def _acc(name):
	"""Resolve an account by its account_name within the demo company."""
	return frappe.db.get_value("Account", {"account_name": name, "company": COMPANY}, "name")


def create_company():
	if frappe.db.exists("Company", COMPANY):
		print(f"SKIP company (exists): {COMPANY}")
		return
	doc = frappe.get_doc({
		"doctype": "Company",
		"company_name": COMPANY,
		"abbr": ABBR,
		"default_currency": CURRENCY,
		"country": COUNTRY,
		# Demo values only - no production CR / VAT registration numbers are used.
		"tax_id": "300000000000003",
		"domain": "Services",
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	print(f"CREATED company: {COMPANY} ({CURRENCY}, {COUNTRY})")


def create_retention_account():
	"""BRD-18: retention withheld is a receivable that is NOT yet collectable."""
	parent = frappe.db.get_value(
		"Account", {"account_name": "Accounts Receivable", "company": COMPANY, "is_group": 1}, "name"
	) or frappe.db.get_value(
		"Account", {"account_name": "Current Assets", "company": COMPANY, "is_group": 1}, "name"
	)
	if not parent:
		print("WARN: could not locate a receivable parent account")
		return
	if _acc("Retention Receivable"):
		print("SKIP account (exists): Retention Receivable")
		return
	frappe.get_doc({
		"doctype": "Account",
		"account_name": "Retention Receivable",
		"parent_account": parent,
		"company": COMPANY,
		"account_type": "Receivable",
		"account_currency": CURRENCY,
		"is_group": 0,
	}).insert(ignore_permissions=True)
	frappe.db.commit()
	print("CREATED account: Retention Receivable")


def create_vat_templates():
	"""BRD-24: standard 15% Saudi VAT, demo configuration."""
	vat_acc = _acc("VAT") or _acc("Output VAT")
	if not vat_acc:
		parent = frappe.db.get_value(
			"Account", {"account_name": "Duties and Taxes", "company": COMPANY, "is_group": 1}, "name"
		)
		if not parent:
			print("WARN: no Duties and Taxes group; skipping VAT account")
			return
		vat_acc = frappe.get_doc({
			"doctype": "Account", "account_name": "Output VAT 15%", "parent_account": parent,
			"company": COMPANY, "account_type": "Tax", "account_currency": CURRENCY, "is_group": 0,
		}).insert(ignore_permissions=True).name
		print("CREATED account: Output VAT 15%")

	tmpl_name = f"KSA VAT 15% - {ABBR}"
	if not frappe.db.exists("Sales Taxes and Charges Template", tmpl_name):
		frappe.get_doc({
			"doctype": "Sales Taxes and Charges Template",
			"title": "KSA VAT 15%",
			"company": COMPANY,
			"is_default": 1,
			"taxes": [{
				"charge_type": "On Net Total",
				"account_head": vat_acc,
				"rate": VAT_RATE,
				"description": "VAT 15%",
			}],
		}).insert(ignore_permissions=True)
		print(f"CREATED sales tax template: {tmpl_name}")

	# Buying side
	in_vat = _acc("Input VAT 15%")
	if not in_vat:
		parent = frappe.db.get_value(
			"Account", {"account_name": "Duties and Taxes", "company": COMPANY, "is_group": 1}, "name"
		)
		in_vat = frappe.get_doc({
			"doctype": "Account", "account_name": "Input VAT 15%", "parent_account": parent,
			"company": COMPANY, "account_type": "Tax", "account_currency": CURRENCY, "is_group": 0,
		}).insert(ignore_permissions=True).name
		print("CREATED account: Input VAT 15%")

	ptmpl = f"KSA Input VAT 15% - {ABBR}"
	if not frappe.db.exists("Purchase Taxes and Charges Template", ptmpl):
		frappe.get_doc({
			"doctype": "Purchase Taxes and Charges Template",
			"title": "KSA Input VAT 15%",
			"company": COMPANY,
			"is_default": 1,
			"taxes": [{
				"charge_type": "On Net Total", "category": "Total", "add_deduct_tax": "Add",
				"account_head": in_vat, "rate": VAT_RATE, "description": "Input VAT 15%",
			}],
		}).insert(ignore_permissions=True)
		print(f"CREATED purchase tax template: {ptmpl}")

	frappe.db.commit()


def execute():
	create_company()
	create_retention_account()
	create_vat_templates()
	print("Company setup complete.")
