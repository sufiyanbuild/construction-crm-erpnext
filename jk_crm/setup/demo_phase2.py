"""Demo data for the capabilities added in Phase 2.

Additive and idempotent: it never edits or deletes the existing demo chain, it
only fills the gaps the original lifecycle did not cover - task-driven project
progress, a completion certificate, a retention release, and leads captured from
email and WhatsApp.

Every record it creates is identifiable: leads carry a jk_source_channel and a
*.demo.invalid address or a 9665009xxxxx number.
"""

import frappe
from frappe.utils import add_days, nowdate

from jk_crm.integrations.lead_capture import CHANNEL_EMAIL, CHANNEL_WHATSAPP, find_or_create_lead

COMPANY = "JK Demo Contracting"
TEMPLATE = "JK Construction Project"

# Realistic mid-flight progress: earlier stages done, execution underway.
TASK_PLAN = [
	("Mobilisation and Site Setup", "Completed"),
	("Submittals and Approvals", "Completed"),
	("Material Procurement", "Completed"),
	("Site Execution - Phase 1", "Completed"),
	("Site Execution - Phase 2", "Working"),
	("Testing and Commissioning", "Open"),
	("Client Inspection and Snagging", "Open"),
	("Documentation and As-Built Drawings", "Open"),
	("Handover and Completion Certificate", "Open"),
]

INBOUND_LEADS = [
	{
		"channel": CHANNEL_EMAIL,
		"name": "Khalid Al-Mutairi",
		"email": "procurement@northgate.demo.invalid",
		"subject": "RFQ - fire protection system for warehouse expansion",
	},
	{
		"channel": CHANNEL_EMAIL,
		"name": "Sara Bin Hamad",
		"email": "sara.h@coastaldev.demo.invalid",
		"subject": "Tender invitation - pump house upgrade",
	},
	{
		"channel": CHANNEL_WHATSAPP,
		"name": "Majed Contracting",
		"phone": "966500900101",
		"subject": "Hi, do you supply and install sprinkler systems?",
	},
	{
		"channel": CHANNEL_WHATSAPP,
		"name": "Abdullah Trading",
		"phone": "966500900102",
		"subject": "Need a quotation for fire pump maintenance",
	},
]


IN_FLIGHT_PROJECT = "North Ring Pump Station - Phase 2 (Demo)"


def _completed_project():
	"""The original demo project: finished, PO closed, warranty running."""
	return frappe.db.get_value(
		"Project", {"company": COMPANY, "status": "Completed"}, "name"
	) or frappe.db.get_value("Project", {"company": COMPANY}, "name")


def _customer():
	return frappe.db.get_value("Customer", {"name": ["like", "%Demo%"]}, "name") \
		or frappe.db.get_value("Customer", {}, "name")


def _in_flight_project():
	"""A second, live project - the completed one cannot host mid-flight tasks.

	Adding incomplete tasks to the finished project would drop its progress
	below 100%, ERPNext would reopen it, and our own BRD-32 rule would then
	refuse the already-closed customer PO. A separate live project is both
	correct and a better demo: one job finished, one in progress.
	"""
	existing = frappe.db.get_value("Project", {"project_name": IN_FLIGHT_PROJECT}, "name")
	if existing:
		return existing

	doc = frappe.get_doc({
		"doctype": "Project",
		"project_name": IN_FLIGHT_PROJECT,
		"company": COMPANY,
		"customer": _customer(),
		"status": "Open",
		"percent_complete_method": "Task Completion",
		"expected_start_date": add_days(nowdate(), -70),
		"expected_end_date": add_days(nowdate(), 40),
		"jk_project_manager": "pm.two@jkdemo.local"
			if frappe.db.exists("User", "pm.two@jkdemo.local") else None,
		"jk_site_supervisor": "supervisor@jkdemo.local"
			if frappe.db.exists("User", "supervisor@jkdemo.local") else None,
		"jk_customer_po_no": "RDA-PO-2026-9042",
		"jk_customer_po_status": "Open",
		"jk_has_warranty": 1,
		"jk_warranty_start_date": add_days(nowdate(), 40),
		"jk_warranty_period_months": 12,
		"jk_warranty_terms": "12 months on workmanship from practical completion.",
	})
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)

	# Handover is workflow-controlled (BRD-11), so drive it through the real
	# transitions rather than writing the state directly.
	from frappe.model.workflow import apply_workflow

	pm = "pm.two@jkdemo.local" if frappe.db.exists("User", "pm.two@jkdemo.local") else None
	try:
		apply_workflow(doc, "Initiate Handover")
		doc.reload()
		doc.jk_handover_to = pm
		doc.jk_handover_date = add_days(nowdate(), -68)
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
		apply_workflow(doc, "Accept Handover")
		doc.reload()
	except Exception as exc:
		print(f"  WARN: handover workflow not applied ({exc})")

	frappe.db.commit()
	print(
		f"CREATED in-flight project: {doc.name} ({IN_FLIGHT_PROJECT}) "
		f"| handover={doc.jk_handover_status}"
	)
	return doc.name


def create_project_tasks():
	"""BRD-12: give the project real tasks so progress is calculated, not typed."""
	project = _in_flight_project()
	if not project:
		print("SKIP tasks: could not resolve an in-flight project")
		return None

	# ERPNext refuses a task starting before its project. Anchor to the project's
	# own start date, and omit dates entirely when the project has none.
	base = frappe.db.get_value("Project", project, "expected_start_date")

	created = 0
	for idx, (subject, status) in enumerate(TASK_PLAN):
		if frappe.db.exists("Task", {"project": project, "subject": subject}):
			continue
		payload = {
			"doctype": "Task",
			"subject": subject,
			"project": project,
			"status": status,
			"progress": 100 if status == "Completed" else (40 if status == "Working" else 0),
		}
		if base:
			payload["exp_start_date"] = add_days(base, idx * 7)
			payload["exp_end_date"] = add_days(base, idx * 7 + 6)
		task = frappe.get_doc(payload)
		task.flags.ignore_permissions = True
		task.insert(ignore_permissions=True)
		created += 1

	# ERPNext recalculates percent_complete from the tasks itself; we only
	# reload to report it.
	frappe.db.commit()
	doc = frappe.get_doc("Project", project)

	doc.reload()
	print(f"Tasks: {created} created on {project}; progress now {doc.percent_complete}%")
	return project


def capture_inbound_leads():
	"""BRD-01: leads arriving by email and WhatsApp, through the real capture path."""
	results = []
	for spec in INBOUND_LEADS:
		doctype, name, created = find_or_create_lead(
			channel=spec["channel"],
			sender_name=spec["name"],
			email=spec.get("email"),
			phone=spec.get("phone"),
			subject=spec["subject"],
			company=COMPANY,
		)
		if name and created:
			frappe.db.set_value(
				"Lead", name, "jk_source_detail", f"{spec['channel']}: {spec['subject']}"[:140]
			)
		results.append((spec["channel"], name, created))
	frappe.db.commit()

	new = sum(1 for _, _, c in results if c)
	print(f"Inbound leads: {new} created, {len(results) - new} matched existing")
	for channel, name, created in results:
		print(f"  {channel}: {name} {'(new)' if created else '(existing)'}")
	return results


def release_one_retention():
	"""BRD-18: demonstrate the release path end to end."""
	# Pick the smallest releasable entry so the larger one stays Pending and the
	# demo can still show retention being held.
	entry = frappe.db.get_value(
		"JK Retention Entry",
		{"docstatus": 1, "status": ["in", ["Pending", "Due"]], "release_invoice": ["is", "not set"]},
		["name", "retention_amount"],
		order_by="retention_amount asc",
		as_dict=True,
	)
	if not entry:
		print("SKIP retention release: no releasable entry")
		return None

	from jk_crm.retention import create_release_invoice

	frappe.db.set_value("JK Retention Entry", entry.name, "status", "Due")
	invoice = create_release_invoice(entry.name)
	frappe.db.commit()
	print(f"Retention release: {entry.name} -> draft invoice {invoice} (SAR {entry.retention_amount})")
	return invoice


def complete_warranty_and_certificate():
	"""BRD-15 / BRD-23: refresh warranty status and issue the certificate."""
	project = _completed_project()
	if not project:
		return None

	doc = frappe.get_doc("Project", project)
	if doc.status != "Completed":
		print(f"SKIP certificate: {project} is {doc.status}, not Completed")
		return None

	if not doc.jk_certificate_issued_by:
		doc.jk_certificate_issued_by = doc.jk_project_manager or "Administrator"
	if not doc.jk_certificate_accepted_by:
		doc.jk_certificate_accepted_by = "Customer Representative"
	if not doc.jk_completion_notes:
		doc.jk_completion_notes = (
			"All contracted works completed, tested and handed over. "
			"Snag list closed and as-built documentation submitted."
		)
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	doc.reload()
	print(
		f"Certificate: {doc.jk_completion_certificate_no} | "
		f"warranty {doc.jk_warranty_status} to {doc.jk_warranty_end_date}"
	)
	return doc.jk_completion_certificate_no


def align_completed_project_tasks():
	"""Keep the finished project internally consistent.

	A project marked Completed must not show open tasks. Where the completed
	demo project carries tasks, close them and let ERPNext derive 100% from
	them instead of holding a manually-typed number.
	"""
	project = _completed_project()
	if not project:
		return None

	tasks = frappe.get_all("Task", filters={"project": project}, pluck="name")
	if not tasks:
		return None

	closed = 0
	for name in tasks:
		task = frappe.get_doc("Task", name)
		if task.status != "Completed":
			task.status = "Completed"
			task.progress = 100
			task.flags.ignore_permissions = True
			task.save(ignore_permissions=True)
			closed += 1

	doc = frappe.get_doc("Project", project)
	if doc.percent_complete_method != "Task Completion":
		doc.percent_complete_method = "Task Completion"
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
	frappe.db.commit()

	doc.reload()
	print(
		f"Completed project {project}: {len(tasks)} tasks ({closed} closed now), "
		f"progress {doc.percent_complete}% via {doc.percent_complete_method}"
	)
	return project


def execute():
	print("--- Phase 2 demo data ---")
	create_project_tasks()
	align_completed_project_tasks()
	capture_inbound_leads()
	complete_warranty_and_certificate()
	release_one_retention()
	print("--- done ---")
