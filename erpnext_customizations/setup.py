# pyrefly: ignore [missing-import]
import frappe

def remove_help_dropdown():
	"""
	Removes standard help dropdown links from Navbar Settings in the database.
	"""
	try:
		navbar_settings = frappe.get_single("Navbar Settings")
		navbar_settings.set("help_dropdown", [])
		navbar_settings.save(ignore_permissions=True)
		frappe.db.commit()
	except Exception as e:
		# Log exception if any, but do not block migration/install
		frappe.log_error(message=frappe.get_traceback(), title="Error removing help dropdown")
