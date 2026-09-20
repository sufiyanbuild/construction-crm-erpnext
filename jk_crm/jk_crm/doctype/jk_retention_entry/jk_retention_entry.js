// Copyright (c) 2026, JK Consultancies and contributors
// For license information, please see license.txt

// UI only (BRD-18). The release itself is decided and performed server-side in
// jk_crm.retention.create_release_invoice - this just offers the button to the
// people allowed to use it.

frappe.ui.form.on("JK Retention Entry", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) {
			return;
		}

		const releasable = ["Pending", "Due"].includes(frm.doc.status);

		if (releasable && !frm.doc.release_invoice) {
			frm.add_custom_button(__("Release Retention"), () => {
				frappe.confirm(
					__("Raise a Retention Release invoice for {0} {1}?", [
						frm.doc.currency || "",
						format_currency(frm.doc.retention_amount),
					]),
					() => {
						frappe.call({
							method: "jk_crm.retention.create_release_invoice",
							args: { retention_entry: frm.doc.name },
							freeze: true,
							freeze_message: __("Creating release invoice..."),
							callback(r) {
								if (r.message) {
									frappe.set_route("Form", "Sales Invoice", r.message);
								}
							},
						});
					}
				);
			}).addClass("btn-primary");
		}

		if (frm.doc.release_invoice) {
			frm.add_custom_button(__("Release Invoice"), () => {
				frappe.set_route("Form", "Sales Invoice", frm.doc.release_invoice);
			}, __("View"));
		}

		if (frm.doc.sales_invoice) {
			frm.add_custom_button(__("Source Invoice"), () => {
				frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice);
			}, __("View"));
		}

		// Make the state obvious without reading the field.
		const colours = {
			Pending: "orange",
			Due: "red",
			Released: "green",
			Cancelled: "grey",
		};
		if (colours[frm.doc.status]) {
			frm.page.set_indicator(__(frm.doc.status), colours[frm.doc.status]);
		}
	},
});
