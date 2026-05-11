"""
POS Invoice Override for POS-Awesome
Combines shift validation and automatic batch splitting for overdraw scenarios.
"""
import frappe
from frappe import _
from frappe.utils import flt

from erpnext.accounts.doctype.pos_invoice.pos_invoice import POSInvoice
from erpnext.stock.doctype.batch.batch import get_batch_qty
from erpnext.stock.serial_batch_bundle import SerialBatchCreation

from posawesome.posawesome.api.invoice import validate_shift


class CustomPOSInvoice(POSInvoice):
	"""Override ERPNext POS Invoice for POS Awesome shift validation and batch splitting."""

	def validate_pos_opening_entry(self):
		"""Allow POS invoices when a POS Awesome shift is open.

		If the invoice references ``posa_pos_opening_shift`` we validate that
		shift using POS Awesome's rules and skip the standard ERPNext
		validation for ``POS Opening Entry``. Otherwise, fall back to the
		default ERPNext behaviour.
		"""
		if getattr(self, "posa_pos_opening_shift", None):
			# Use existing shift validation from POS Awesome
			validate_shift(self)
			return

		# No POS Awesome shift - use ERPNext's validation
		super().validate_pos_opening_entry()

	def before_validate(self):
		if self._action == "submit":
			self.use_auto_batch_bundle_for_overdrawn_rows()

		super_before_validate = getattr(super(), "before_validate", None)
		if super_before_validate:
			super_before_validate()

	def use_auto_batch_bundle_for_overdrawn_rows(self):
		"""Auto-split batches when selected batch has insufficient qty."""
		if self.is_return:
			return

		# Track consumption per (item_code, warehouse, batch_no) within this invoice
		consumed_in_doc = {}

		for row in self.items:
			if not should_auto_split_batch(row):
				continue

			if not row.get("warehouse") and self.get("set_warehouse"):
				row.warehouse = self.set_warehouse

			batch_no = row.get("batch_no")
			key = (row.get("item_code"), row.get("warehouse"), batch_no)
			already = flt(consumed_in_doc.get(key, 0))

			selected_batch_qty = max(0.0, get_selected_batch_qty(row) - already)
			required_qty = flt(row.stock_qty or row.qty)
			if selected_batch_qty >= required_qty:
				consumed_in_doc[key] = already + required_qty
				continue

			consumed_for_row_item_wh = {
				bn: qty
				for (ic, wh, bn), qty in consumed_in_doc.items()
				if ic == row.get("item_code") and wh == row.get("warehouse") and bn
			}
			bundle, allocations = make_auto_batch_bundle(
				self, row, required_qty, consumed_by_batch=consumed_for_row_item_wh
			)
			if not bundle:
				frappe.throw(
					_(
						"Batch {0} for item {1} is not available in warehouse {2}. Required qty {3}."
					).format(
						frappe.bold(row.batch_no),
						frappe.bold(row.item_code),
						frappe.bold(row.warehouse or ""),
						frappe.bold(required_qty),
					),
					title=_("Not Available"),
				)

			row.serial_and_batch_bundle = bundle.name
			row.batch_no = None
			row.use_serial_batch_fields = 0

			# Record consumption across batches used by the bundle
			for bn, qty in (allocations or {}).items():
				k = (row.get("item_code"), row.get("warehouse"), bn)
				consumed_in_doc[k] = flt(consumed_in_doc.get(k, 0)) + flt(qty)


def should_auto_split_batch(row):
	"""Check if row needs auto batch splitting."""
	if not row.get("item_code") or not row.get("batch_no") or row.get("serial_and_batch_bundle"):
		return False

	item = frappe.get_cached_value("Item", row.item_code, ["has_batch_no", "has_serial_no"], as_dict=True)
	return bool(item and item.has_batch_no and not item.has_serial_no)


def get_selected_batch_qty(row):
	"""Get safe batch qty using ledger-based calculation."""
	if not row.get("batch_no"):
		return 0
	return max(0.0, flt(get_sbb_safe_batch_qty(row, row.batch_no)))


def make_auto_batch_bundle(doc, row, required_qty, consumed_by_batch=None):
	"""Create Serial & Batch Bundle with auto-allocated batches."""
	batches = get_batch_allocations(row, required_qty, consumed_by_batch=consumed_by_batch)
	bundle = SerialBatchCreation(
		{
			"item_code": row.item_code,
			"warehouse": row.warehouse,
			"qty": required_qty,
			"actual_qty": required_qty,
			"posting_date": doc.posting_date,
			"posting_time": doc.posting_time,
			"voucher_type": doc.doctype,
			"voucher_no": doc.name,
			"voucher_detail_no": row.name,
			"company": doc.company,
			"type_of_transaction": "Outward",
			"batches": batches,
			"do_not_submit": True,
		}
	).make_serial_and_batch_bundle()

	return (bundle, batches) if bundle and bundle.get("name") else (None, batches)


def get_batch_allocations(row, required_qty, consumed_by_batch=None):
	"""Allocate batches using FIFO/FEFO with ledger-based validation."""
	remaining_qty = flt(required_qty)
	allocations = frappe._dict()
	consumed_by_batch = consumed_by_batch or {}

	for batch in get_batch_qty(item_code=row.item_code, warehouse=row.warehouse):
		if remaining_qty <= 0:
			break

		available_qty = min(flt(batch.qty), get_sbb_safe_batch_qty(row, batch.batch_no))
		available_qty -= flt(consumed_by_batch.get(batch.batch_no, 0))
		if available_qty <= 0:
			continue

		qty = min(available_qty, remaining_qty)
		allocations[batch.batch_no] = qty
		remaining_qty -= qty

	return allocations


def get_sbb_safe_batch_qty(row, batch_no):
	"""Get batch qty using same basis as Serial & Batch Bundle validation."""
	return flt(get_submitted_sbb_qty(row, batch_no)) + flt(get_old_batch_ledger_qty(row, batch_no))


def get_submitted_sbb_qty(row, batch_no):
	"""Get batch qty from submitted Serial & Batch Bundles."""
	result = frappe.db.sql(
		"""
		SELECT SUM(sbe.qty)
		FROM `tabSerial and Batch Entry` sbe
		INNER JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sbe.parent
		WHERE sbb.docstatus = 1
			AND sbb.is_cancelled = 0
			AND sbb.item_code = %s
			AND sbb.warehouse = %s
			AND sbe.batch_no = %s
		""",
		(row.item_code, row.warehouse, batch_no),
	)
	return flt(result[0][0]) if result else 0


def get_old_batch_ledger_qty(row, batch_no):
	"""Get batch qty from legacy Stock Ledger Entries (without bundle)."""
	result = frappe.db.sql(
		"""
		SELECT SUM(actual_qty)
		FROM `tabStock Ledger Entry`
		WHERE is_cancelled = 0
			AND item_code = %s
			AND warehouse = %s
			AND batch_no = %s
			AND serial_and_batch_bundle IS NULL
		""",
		(row.item_code, row.warehouse, batch_no),
	)
	return flt(result[0][0]) if result else 0
