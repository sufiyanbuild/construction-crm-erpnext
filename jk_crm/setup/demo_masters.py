import frappe

COMPANY = "JK Demo Contracting"
ABBR = "JKD"
CUSTOMER = "Riyadh Development Authority (Demo)"
SUPPLIER = "Gulf Mechanical Supplies (Demo)"

ITEMS = [
	{"item_code": "FP-PUMP-200", "item_name": "Fire Pump Unit FP-200", "is_stock_item": 1,
	 "stock_uom": "Nos", "rate": 48000},
	{"item_code": "FP-INSTALL", "item_name": "Installation and Commissioning Service", "is_stock_item": 0,
	 "stock_uom": "Nos", "rate": 95000},
	{"item_code": "FP-SUBCON", "item_name": "Subcontracted Piping Works", "is_stock_item": 0,
	 "stock_uom": "Nos", "rate": 62000},
	{"item_code": "FP-VAR-TANK", "item_name": "Additional Water Storage Tank (Variation)", "is_stock_item": 0,
	 "stock_uom": "Nos", "rate": 41000},
]

# BRD-20: the three address concepts the BRD calls out, kept distinct.
ADDRESSES = [
	{"address_title": "RDA Head Office", "address_type": "Office",
	 "address_line1": "King Fahd Road, Al Olaya District", "city": "Riyadh",
	 "country": "Saudi Arabia", "is_primary_address": 1, "tag": "legal"},
	{"address_title": "RDA Finance Dept", "address_type": "Billing",
	 "address_line1": "Finance Building, Gate 3, Al Olaya", "city": "Riyadh",
	 "country": "Saudi Arabia", "is_shipping_address": 0, "tag": "billing"},
	{"address_title": "RDA Site - North Ring", "address_type": "Shipping",
	 "address_line1": "North Ring Road Pump Station, Plot 214", "city": "Riyadh",
	 "country": "Saudi Arabia", "is_shipping_address": 1, "tag": "site"},
]


def ensure_uom():
	if not frappe.db.exists("UOM", "Nos"):
		frappe.get_doc({"doctype": "UOM", "uom_name": "Nos"}).insert(ignore_permissions=True)


def ensure_item_group():
	if not frappe.db.exists("Item Group", "Fire Protection Systems"):
		parent = frappe.db.get_value("Item Group", {"is_group": 1, "parent_item_group": ""}, "name") \
			or "All Item Groups"
		frappe.get_doc({"doctype": "Item Group", "item_group_name": "Fire Protection Systems",
			"parent_item_group": parent, "is_group": 0}).insert(ignore_permissions=True)
		print("CREATED item group: Fire Protection Systems")


def create_items():
	for spec in ITEMS:
		if frappe.db.exists("Item", spec["item_code"]):
			continue
		payload = {
			"doctype": "Item",
			"item_code": spec["item_code"],
			"item_name": spec["item_name"],
			"item_group": "Fire Protection Systems",
			"stock_uom": spec["stock_uom"],
			"is_stock_item": spec["is_stock_item"],
			"is_purchase_item": 1,
			"is_sales_item": 1,
		}
		# Only stock items carry a default warehouse; leaving it blank on a
		# service item lets the global Stock Settings default (another company's
		# warehouse on this shared site) leak in and fail validation.
		if spec["is_stock_item"]:
			payload["item_defaults"] = [{"company": COMPANY, "default_warehouse": f"Stores - {ABBR}"}]
		frappe.get_doc(payload).insert(ignore_permissions=True)
		print(f"CREATED item: {spec['item_code']}")
	frappe.db.commit()


def create_customer():
	if not frappe.db.exists("Customer", CUSTOMER):
		frappe.get_doc({
			"doctype": "Customer", "customer_name": CUSTOMER,
			"customer_type": "Company", "customer_group": "Commercial",
			"territory": "All Territories", "default_currency": "SAR",
			"tax_id": "310000000000003",  # demo VAT number only
			"jk_cr_number": "1010000000",
		}).insert(ignore_permissions=True)
		print(f"CREATED customer: {CUSTOMER}")

	created = {}
	for spec in ADDRESSES:
		tag = spec.pop("tag")
		existing = frappe.db.get_value("Address", {"address_title": spec["address_title"]}, "name")
		if existing:
			created[tag] = existing
			continue
		addr = frappe.get_doc({
			"doctype": "Address", **spec,
			"links": [{"link_doctype": "Customer", "link_name": CUSTOMER}],
		})
		addr.insert(ignore_permissions=True)
		created[tag] = addr.name
		print(f"CREATED address ({tag}): {addr.name}")

	if created.get("legal"):
		frappe.db.set_value("Customer", CUSTOMER, "jk_legal_entity_address", created["legal"])

	if not frappe.db.exists("Contact", {"first_name": "Mansour", "last_name": "Al-Dossary"}):
		c = frappe.get_doc({
			"doctype": "Contact", "first_name": "Mansour", "last_name": "Al-Dossary",
			"designation": "Projects Director",
			"links": [{"link_doctype": "Customer", "link_name": CUSTOMER}],
			"email_ids": [{"email_id": "m.aldossary@rda-demo.local", "is_primary": 1}],
			"phone_nos": [{"phone": "+966500000001", "is_primary_phone": 1}],
		})
		c.insert(ignore_permissions=True)
		print(f"CREATED contact: {c.name}")

	frappe.db.commit()
	return created


def create_supplier():
	if frappe.db.exists("Supplier", SUPPLIER):
		return
	frappe.get_doc({
		"doctype": "Supplier", "supplier_name": SUPPLIER,
		"supplier_group": "Services", "supplier_type": "Company",
		"country": "Saudi Arabia", "default_currency": "SAR",
	}).insert(ignore_permissions=True)
	frappe.db.commit()
	print(f"CREATED supplier: {SUPPLIER}")


def execute():
	ensure_uom()
	ensure_item_group()
	create_items()
	addrs = create_customer()
	create_supplier()
	print(f"Masters complete. Addresses: {addrs}")
	return addrs
