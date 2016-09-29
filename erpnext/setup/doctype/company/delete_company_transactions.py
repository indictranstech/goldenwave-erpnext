# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import cint
from frappe import _
from frappe.desk.notifications import clear_notifications

@frappe.whitelist()
def delete_company_transactions(company_name):
	frappe.only_for("System Manager")
	doc = frappe.get_doc("Company", company_name)

	if frappe.session.user != doc.owner:
		frappe.throw(_("Transactions can only be deleted by the creator of the Company"), 
			frappe.PermissionError)

	delete_bins(company_name)
	delete_lead_addresses(company_name)

	for doctype in frappe.db.sql_list("""select parent from
		tabDocField where fieldtype='Link' and options='Company'"""):
		if doctype not in ("Account", "Cost Center", "Warehouse", "Budget",
			"Party Account", "Employee", "Sales Taxes and Charges Template",
			"Purchase Taxes and Charges Template", "POS Profile", 'BOM'):
				delete_for_doctype(doctype, company_name)

	# Clear notification counts
	clear_notifications()

def delete_for_doctype(doctype, company_name):
	meta = frappe.get_meta(doctype)
	company_fieldname = meta.get("fields", {"fieldtype": "Link",
		"options": "Company"})[0].fieldname

	if not meta.issingle:
		if not meta.istable:
			# delete children
			for df in meta.get_table_fields():
				frappe.db.sql("""delete from `tab{0}` where parent in
					(select name from `tab{1}` where `{2}`=%s)""".format(df.options,
						doctype, company_fieldname), company_name)

		# delete parent
		frappe.db.sql("""delete from `tab{0}`
			where {1}= %s """.format(doctype, company_fieldname), company_name)

		# reset series
		naming_series = meta.get_field("naming_series")
		if naming_series and naming_series.options:
			prefixes = sorted(naming_series.options.split("\n"), lambda a, b: len(b) - len(a))

			for prefix in prefixes:
				if prefix:
					last = frappe.db.sql("""select max(name) from `tab{0}`
						where name like %s""".format(doctype), prefix + "%")
					if last and last[0][0]:
						last = cint(last[0][0].replace(prefix, ""))
					else:
						last = 0

					frappe.db.sql("""update tabSeries set current = %s
						where name=%s""", (last, prefix))


def delete_bins(company_name):
	frappe.db.sql("""delete from tabBin where warehouse in
			(select name from tabWarehouse where company=%s)""", company_name)

def delete_lead_addresses(company_name):
	"""Delete addresses to which leads are linked"""
	for lead in frappe.get_all("Lead", filters={"company": company_name}):
		frappe.db.sql("""delete from `tabAddress`
			where lead=%s and (customer='' or customer is null) and (supplier='' or supplier is null)""", lead.name)

		frappe.db.sql("""update `tabAddress` set lead=null, lead_name=null where lead=%s""", lead.name)
