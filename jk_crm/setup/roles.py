"""Roles (product) and demo users (demo only).

create_roles() is product configuration and runs on install. create_users(),
create_sales_persons() and execute() are DEMO ONLY - they create eleven
fictional users and must never be run on a client site. install.py deliberately
calls only create_roles().
"""

import frappe

# Demo company, used only by the demo-only functions below. Resolved from
# settings so a demo on a differently-named company still pins users correctly.
DEMO_COMPANY = "JK Demo Contracting"


def _company():
	from jk_crm.utils import get_default_company

	return get_default_company() or DEMO_COMPANY

# BRD section 3 user groups -> a JK role that carries the departmental meaning,
# paired with the stock ERPNext roles that actually grant doctype access.
ROLE_MAP = {
	"JK Sales User": ["Sales User", "Sales Manager"],
	"JK Estimation Engineer": ["Sales User"],
	"JK Technical User": ["Projects User"],
	"JK Project Manager": ["Projects Manager", "Projects User"],
	"JK Site Supervisor": ["Projects User"],
	"JK Finance User": ["Accounts User", "Accounts Manager"],
	"JK Procurement User": ["Purchase User", "Purchase Manager"],
	"JK Management": ["Sales Manager", "Projects Manager", "Accounts Manager", "Purchase Manager"],
}

# DEMO ONLY. BRD-29 asks for a minimum of 10 accounts; these eleven demonstrate
# that on the demo site. The client's real user list is an open BRD point.
USERS = [
	("sales.manager@jkdemo.local", "Omar", "Al-Harbi", "JK Sales User"),
	("sales.exec@jkdemo.local", "Layla", "Siddiqui", "JK Sales User"),
	("estimation.lead@jkdemo.local", "Faisal", "Rahman", "JK Estimation Engineer"),
	("estimation.eng@jkdemo.local", "Noura", "Khalid", "JK Estimation Engineer"),
	("technical@jkdemo.local", "Yousef", "Malik", "JK Technical User"),
	("pm.one@jkdemo.local", "Ahmed", "Zaid", "JK Project Manager"),
	("pm.two@jkdemo.local", "Salma", "Idris", "JK Project Manager"),
	("supervisor@jkdemo.local", "Tariq", "Nasser", "JK Site Supervisor"),
	("finance@jkdemo.local", "Hana", "Qureshi", "JK Finance User"),
	("procurement@jkdemo.local", "Bilal", "Othman", "JK Procurement User"),
	("management@jkdemo.local", "Ibrahim", "Saleh", "JK Management"),
]


def create_roles():
	for role in ROLE_MAP:
		if frappe.db.exists("Role", role):
			continue
		frappe.get_doc({
			"doctype": "Role", "role_name": role, "desk_access": 1,
		}).insert(ignore_permissions=True)
		print(f"CREATED role: {role}")
	frappe.db.commit()


def create_users():
	"""DEMO ONLY - creates fictional users. Never run on a client site."""
	for email, first, last, jk_role in USERS:
		if frappe.db.exists("User", email):
			user = frappe.get_doc("User", email)
		else:
			user = frappe.get_doc({
				"doctype": "User", "email": email, "first_name": first, "last_name": last,
				"send_welcome_email": 0, "user_type": "System User", "enabled": 1,
			})
			user.insert(ignore_permissions=True)
			print(f"CREATED user: {email} ({jk_role})")

		wanted = set([jk_role] + ROLE_MAP[jk_role] + ["Employee"])
		existing = {r.role for r in user.roles}
		for role in wanted - existing:
			if frappe.db.exists("Role", role):
				user.append("roles", {"role": role})
		user.save(ignore_permissions=True)

		# BRD-29 departmental visibility: pin every demo user to the demo company.
		company = _company()
		if not frappe.db.exists("User Permission",
				{"user": email, "allow": "Company", "for_value": company}):
			frappe.get_doc({
				"doctype": "User Permission", "user": email,
				"allow": "Company", "for_value": company, "apply_to_all_doctypes": 1,
			}).insert(ignore_permissions=True)
	frappe.db.commit()


def create_sales_persons():
	"""DEMO ONLY. BRD-03: representative assignment needs Sales Person records."""
	root = frappe.db.get_value("Sales Person", {"is_group": 1, "parent_sales_person": ""}, "name") \
		or frappe.db.get_value("Sales Person", {"is_group": 1}, "name")
	for email, first, last, jk_role in USERS:
		if jk_role != "JK Sales User":
			continue
		sp_name = f"{first} {last}"
		if frappe.db.exists("Sales Person", sp_name):
			continue
		frappe.get_doc({
			"doctype": "Sales Person", "sales_person_name": sp_name,
			"parent_sales_person": root, "is_group": 0, "enabled": 1,
		}).insert(ignore_permissions=True)
		print(f"CREATED sales person: {sp_name}")
	frappe.db.commit()


def execute():
	"""DEMO ONLY - full demo user provisioning. install.py calls create_roles()."""
	create_roles()
	create_users()
	create_sales_persons()
	print(f"Roles/users complete: {len(ROLE_MAP)} roles, {len(USERS)} users.")
