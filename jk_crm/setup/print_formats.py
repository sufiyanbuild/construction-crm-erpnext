"""Project completion certificate (BRD-15).

A Print Format on Project rather than a new doctype: the certificate is a
statement about a project that already holds every fact it needs - code,
customer, dates, PM, warranty - so a parallel record would only duplicate and
drift. Issuing is driven by project completion in controllers._apply_completion.

❓ Layout, wording and signatories are an open BRD point. This is a defensible
default, not a client-approved template.
"""

import frappe

FORMAT_NAME = "JK Project Completion Certificate"

HTML = """
<div style="font-family: Arial, Helvetica, sans-serif; color:#1a1a1a;">
  <div style="text-align:center; border-bottom:3px double #333; padding-bottom:12px; margin-bottom:24px;">
    <h2 style="margin:0; letter-spacing:1px;">PROJECT COMPLETION CERTIFICATE</h2>
    <div style="font-size:11px; color:#666; margin-top:6px;">
      Certificate No: <strong>{{ doc.jk_completion_certificate_no or "—" }}</strong>
    </div>
  </div>

  <table style="width:100%; font-size:12px; border-collapse:collapse;">
    <tr>
      <td style="padding:6px 0; width:34%; color:#555;">Project Code</td>
      <td style="padding:6px 0;"><strong>{{ doc.jk_project_code or "—" }}</strong></td>
    </tr>
    <tr>
      <td style="padding:6px 0; color:#555;">Project Name</td>
      <td style="padding:6px 0;"><strong>{{ doc.project_name or doc.name }}</strong></td>
    </tr>
    <tr>
      <td style="padding:6px 0; color:#555;">Customer</td>
      <td style="padding:6px 0;">{{ doc.customer or "—" }}</td>
    </tr>
    <tr>
      <td style="padding:6px 0; color:#555;">Customer Purchase Order</td>
      <td style="padding:6px 0;">{{ doc.jk_customer_po_no or "—" }}</td>
    </tr>
    <tr>
      <td style="padding:6px 0; color:#555;">Site Address</td>
      <td style="padding:6px 0;">{{ doc.jk_site_address or "—" }}</td>
    </tr>
    <tr>
      <td style="padding:6px 0; color:#555;">Completion Date</td>
      <td style="padding:6px 0;"><strong>{{ frappe.format(doc.jk_completion_date, {"fieldtype": "Date"}) }}</strong></td>
    </tr>
    <tr>
      <td style="padding:6px 0; color:#555;">Project Manager</td>
      <td style="padding:6px 0;">{{ frappe.db.get_value("User", doc.jk_project_manager, "full_name") if doc.jk_project_manager else "—" }}</td>
    </tr>
  </table>

  {% if doc.jk_has_warranty %}
  <div style="margin-top:22px; padding:12px 14px; background:#f5f7f9; border-left:3px solid #1d5fa6;">
    <div style="font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:#1d5fa6; margin-bottom:6px;">
      Warranty / Guarantee
    </div>
    <table style="width:100%; font-size:12px;">
      <tr>
        <td style="width:34%; color:#555;">Warranty Period</td>
        <td>{{ doc.jk_warranty_period_months or "—" }} months</td>
      </tr>
      <tr>
        <td style="color:#555;">Warranty From</td>
        <td>{{ frappe.format(doc.jk_warranty_start_date, {"fieldtype": "Date"}) }}</td>
      </tr>
      <tr>
        <td style="color:#555;">Warranty Until</td>
        <td><strong>{{ frappe.format(doc.jk_warranty_end_date, {"fieldtype": "Date"}) }}</strong></td>
      </tr>
      {% if doc.jk_warranty_terms %}
      <tr>
        <td style="color:#555; vertical-align:top;">Terms</td>
        <td>{{ doc.jk_warranty_terms }}</td>
      </tr>
      {% endif %}
    </table>
  </div>
  {% endif %}

  {% if doc.jk_completion_notes %}
  <div style="margin-top:20px; font-size:12px;">
    <div style="color:#555; margin-bottom:4px;">Completion Notes</div>
    <div>{{ doc.jk_completion_notes }}</div>
  </div>
  {% endif %}

  <p style="margin-top:26px; font-size:12px; line-height:1.6;">
    This is to certify that the works described above have been completed in
    accordance with the agreed scope and handed over to the customer.
  </p>

  <table style="width:100%; margin-top:48px; font-size:12px;">
    <tr>
      <td style="width:50%; padding-right:24px;">
        <div style="border-top:1px solid #333; padding-top:6px;">
          Issued By<br>
          <strong>{{ frappe.db.get_value("User", doc.jk_certificate_issued_by, "full_name") if doc.jk_certificate_issued_by else "" }}</strong><br>
          <span style="color:#666;">{{ doc.company }}</span>
        </div>
      </td>
      <td style="width:50%;">
        <div style="border-top:1px solid #333; padding-top:6px;">
          Accepted By (Customer)<br>
          <strong>{{ doc.jk_certificate_accepted_by or "" }}</strong><br>
          <span style="color:#666;">{{ doc.customer or "" }}</span>
        </div>
      </td>
    </tr>
  </table>
</div>
"""


def execute():
	if frappe.db.exists("Print Format", FORMAT_NAME):
		frappe.delete_doc("Print Format", FORMAT_NAME, force=1, ignore_permissions=True)

	frappe.get_doc({
		"doctype": "Print Format",
		"name": FORMAT_NAME,
		"doc_type": "Project",
		"module": "JK CRM",
		"standard": "No",
		"custom_format": 1,
		"print_format_type": "Jinja",
		"html": HTML,
		"disabled": 0,
	}).insert(ignore_permissions=True)
	frappe.db.commit()
	print(f"CREATED print format: {FORMAT_NAME}")
