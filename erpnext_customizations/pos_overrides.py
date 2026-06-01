"""
POS Performance Overrides

Server-side overrides to eliminate unnecessary API calls in the POS workflow.
"""

import frappe
from frappe.utils import flt


@frappe.whitelist()
def get_loyalty_programs(customer):
	"""
	Override for erpnext.accounts.doctype.sales_invoice.sales_invoice.get_loyalty_programs

	Returns an empty list immediately instead of querying the database.
	This is called twice per customer selection in POS, saving ~240ms total.

	If you ever enable loyalty programs, remove the override_whitelisted_methods
	entry in hooks.py for this function.
	"""
	return []


@frappe.whitelist()
def get_stock_availability(item_code, warehouse):
	"""
	Override for erpnext.accounts.doctype.pos_invoice.pos_invoice.get_stock_availability

	The original function calls get_pos_reserved_qty() which performs an expensive
	JOIN + SUM across all submitted, unconsolidated POS Invoices. On sites with many
	open POS invoices, this query can take 1-13+ seconds per item.

	This override:
	  - Reads stock directly from tabBin (simple indexed lookup, ~1ms)
	  - Skips the expensive reserved qty calculation
	  - Returns is_negative_stock_allowed=True so the POS never blocks on stock

	Stock validation still happens server-side at submit time via
	validate_stock_availablility() on the POS Invoice doctype, so overselling
	is still caught before the invoice is finalized.

	To restore the original behavior, remove the override_whitelisted_methods
	entry in hooks.py for this function.
	"""
	is_stock_item = frappe.db.get_value("Item", item_code, "is_stock_item")

	if is_stock_item:
		# Fast path: read directly from tabBin (indexed on item_code + warehouse)
		bin_qty = frappe.db.get_value(
			"Bin",
			{"item_code": item_code, "warehouse": warehouse},
			"actual_qty"
		)
		return flt(bin_qty), True, True  # qty, is_stock_item, is_negative_stock_allowed=True

	# Non-stock / service item
	if frappe.db.exists("Product Bundle", {"name": item_code, "disabled": 0}):
		return 0, True, True

	return 0, False, True
