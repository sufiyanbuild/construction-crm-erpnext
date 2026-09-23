"""Project execution configuration (BRD-12).

Progress measurement is standard ERPNext: Project.percent_complete_method
supports Manual, Task Completion, Task Progress and Task Weight, and the
framework recalculates percent_complete whenever a Task changes. Nothing here
reimplements that - we only supply the construction task structure ERPNext
needs in order to have something to measure, via a standard Project Template.

❓ Which method the client wants is an open BRD point. We ship Task Completion
(ERPNext's own default) rather than inventing a weighting scheme, and the method
remains editable per project.
"""

import frappe

TEMPLATE = "JK Construction Project"

# A contracting job's standard stages. Weights are deliberately left unset so
# the default Task Completion method treats every stage equally until the client
# tells us how they weight them.
TASKS = [
	("Mobilisation and Site Setup", 0),
	("Submittals and Approvals", 5),
	("Material Procurement", 10),
	("Site Execution - Phase 1", 20),
	("Site Execution - Phase 2", 40),
	("Testing and Commissioning", 60),
	("Client Inspection and Snagging", 70),
	("Documentation and As-Built Drawings", 80),
	("Handover and Completion Certificate", 85),
]


def create_task_template():
	"""A standard Project Template carrying the construction stages."""
	if frappe.db.exists("Project Template", TEMPLATE):
		print(f"SKIP project template (exists): {TEMPLATE}")
		return TEMPLATE

	task_names = []
	for subject, offset in TASKS:
		existing = frappe.db.get_value("Task", {"subject": subject, "is_template": 1}, "name")
		if existing:
			task_names.append(existing)
			continue
		task = frappe.get_doc({
			"doctype": "Task",
			"subject": subject,
			"is_template": 1,
			"start": offset,
			"duration": 10,
			"status": "Template",
		})
		task.flags.ignore_permissions = True
		task.insert(ignore_permissions=True)
		task_names.append(task.name)

	doc = frappe.get_doc({
		"doctype": "Project Template",
		# Project Template uses prompt autonaming, so the name must be explicit.
		"name": TEMPLATE,
		"project_template_name": TEMPLATE,
		"tasks": [{"task": name} for name in task_names],
	})
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	print(f"CREATED project template: {TEMPLATE} ({len(task_names)} stages)")
	return TEMPLATE


def set_progress_method(method="Task Completion"):
	"""Make task-driven progress the default for new projects.

	Applied as a Property Setter on the standard field, which is the supported
	way to change a stock default without touching ERPNext core.
	"""
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	make_property_setter(
		"Project", "percent_complete_method", "default", method, "Select",
		validate_fields_for_doctype=False,
	)
	frappe.db.commit()
	print(f"Project progress method default set to: {method}")


def execute():
	create_task_template()
	set_progress_method()
	print("Project execution configuration complete (BRD-12).")
