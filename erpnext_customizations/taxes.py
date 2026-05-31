import frappe
from frappe.utils import flt, cint

def fix_inclusive_tax_rounding(doc, method=None):
	"""
	Fixes rounding issues where Net Total + Tax != Total for inclusive taxes.
	ERPNext calculates tax based on the rounded net total, which can cause 
	a 0.01 discrepancy between the printed grand total and the sum of net + tax.
	"""
	if not doc.get("taxes"):
		return
		
	# Check if there is any inclusive tax
	has_inclusive = any(cint(t.included_in_print_rate) for t in doc.get("taxes"))
	if not has_inclusive:
		return
		
	# ERPNext calculates grand_total properly (Gross Total - Discounts)
	# and stores the difference in grand_total_diff.
	# We want to adjust the tax_amount of the last inclusive tax row so that
	# doc.net_total + doc.total_taxes_and_charges exactly equals doc.grand_total.
	
	expected_total_taxes = flt(doc.grand_total - doc.net_total, doc.precision("total_taxes_and_charges"))
	diff = flt(expected_total_taxes - doc.total_taxes_and_charges, doc.precision("total_taxes_and_charges"))
	
	if diff != 0.0:
		# Find the last inclusive tax row to adjust
		for tax in reversed(doc.get("taxes")):
			if cint(tax.included_in_print_rate):
				tax.tax_amount = flt(tax.tax_amount + diff, tax.precision("tax_amount"))
				tax.tax_amount_after_discount_amount = flt(tax.tax_amount_after_discount_amount + diff, tax.precision("tax_amount"))
				
				# Also update base amounts if applicable
				if hasattr(doc, "conversion_rate") and doc.conversion_rate:
					base_diff = flt(diff * doc.conversion_rate, tax.precision("base_tax_amount"))
					tax.base_tax_amount = flt(tax.base_tax_amount + base_diff, tax.precision("base_tax_amount"))
					tax.base_tax_amount_after_discount_amount = flt(tax.base_tax_amount_after_discount_amount + base_diff, tax.precision("base_tax_amount"))
				
				break
				
		# Update document total taxes
		doc.total_taxes_and_charges = expected_total_taxes
		if hasattr(doc, "base_grand_total") and hasattr(doc, "base_net_total"):
			doc.base_total_taxes_and_charges = flt(doc.base_grand_total - doc.base_net_total, doc.precision("base_total_taxes_and_charges"))
			
		# Recalculate running totals in the taxes table
		running_total = doc.net_total
		running_base_total = getattr(doc, "base_net_total", 0.0)
		
		for tax in doc.get("taxes"):
			running_total = flt(running_total + tax.tax_amount_after_discount_amount, tax.precision("total"))
			tax.total = running_total
			
			if hasattr(tax, "base_tax_amount_after_discount_amount"):
				running_base_total = flt(running_base_total + tax.base_tax_amount_after_discount_amount, tax.precision("base_total"))
				tax.base_total = running_base_total
