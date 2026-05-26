# pyrefly: ignore [missing-import]
import frappe

def remove_help_dropdown():
	"""
	Removes standard help dropdown links from Navbar Settings in the database
	and configures global default FavIcon and Splash Image branding from erpnext_customizations.
	"""
	# 1. Clean Help Dropdown items
	try:
		navbar_settings = frappe.get_single("Navbar Settings")
		navbar_settings.set("help_dropdown", [])
		navbar_settings.save(ignore_permissions=True)
	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(), title="Error removing help dropdown")

	# 2. Configure General Branding Fallbacks (FavIcon & Splash/Loader Image)
	try:
		website_settings = frappe.get_single("Website Settings")
		website_settings.favicon = "/assets/erpnext_customizations/images/astra-logo.ico"
		website_settings.splash_image = "/assets/erpnext_customizations/images/astra-logo.jpg"
		website_settings.save(ignore_permissions=True)
	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(), title="Error configuring Website Settings default branding")

	# Commit database changes
	try:
		frappe.db.commit()
	except Exception as e:
		pass

