/**
 * POS Performance Optimizations
 *
 * Addresses three performance issues in the POS:
 * 1. Duplicate get_party_details calls when selecting a customer (~530ms saved)
 * 2. UI freeze/grey-out during API calls (perceived performance improvement)
 *
 * These hooks run on POS Invoice doctype which is used by the POS page.
 */

frappe.ui.form.on("POS Invoice", {
	onload(frm) {
		_deduplicate_get_party_details(frm);
		_disable_pos_freeze();
	},
});

/**
 * When a customer is selected in POS, get_party_details is called twice:
 * once by the POS module's onchange handler and once by the Sales Invoice
 * controller's customer() method. This wraps the function to skip the
 * second call while the first is still in flight.
 */
function _deduplicate_get_party_details(frm) {
	if (frm._party_details_patched) return;
	frm._party_details_patched = true;

	const original_fn = erpnext.utils.get_party_details;
	if (!original_fn) return;

	erpnext.utils.get_party_details = function (frm, method, args, callback) {
		if (frm._fetching_party_details) {
			console.log("[POS Perf] Skipped duplicate get_party_details call");
			return;
		}
		frm._fetching_party_details = true;

		const wrapped_callback = function () {
			frm._fetching_party_details = false;
			if (callback) callback.apply(this, arguments);
		};

		// Also clear the flag after a timeout as a safety net,
		// in case the request fails without calling the callback
		setTimeout(() => {
			frm._fetching_party_details = false;
		}, 5000);

		return original_fn(frm, method, args, wrapped_callback);
	};
}

/**
 * The POS page greys out during API calls because frappe.call uses
 * freeze: true by default. This overrides frappe.call to disable
 * the freeze overlay when on the POS page, making the UI feel
 * significantly more responsive.
 */
function _disable_pos_freeze() {
	if (frappe._pos_freeze_patched) return;
	frappe._pos_freeze_patched = true;

	const _original_call = frappe.call;
	frappe.call = function (opts) {
		if (
			cur_page &&
			cur_page.page &&
			cur_page.page.page_name === "point-of-sale"
		) {
			opts.freeze = false;
		}
		return _original_call.call(this, opts);
	};
}
