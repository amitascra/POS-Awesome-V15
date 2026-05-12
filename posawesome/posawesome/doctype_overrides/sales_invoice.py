"""
Sales Invoice Override for POS-Awesome
Handles automatic batch splitting for POS-created Sales Invoices.
"""
import frappe
from frappe import _
from frappe.utils import flt, cint

from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from erpnext.stock.doctype.batch.batch import get_batch_qty
from erpnext.stock.serial_batch_bundle import SerialBatchCreation as ERPNextSerialBatchCreation


class CustomSerialBatchCreation(ERPNextSerialBatchCreation):
	"""Custom SerialBatchCreation that skips qty validation for POS invoices.

	POSAwesome handles batch allocation separately via set_batch_nos_for_bundels,
	so we bypass ERPNext's strict bundle validation to prevent false positives.
	"""

	def validate_qty(self, doc):
		# Skip validation for POS invoices - POSAwesome handles batch allocation separately
		if doc.voucher_type in ["Sales Invoice", "POS Invoice"]:
			try:
				voucher_doc = frappe.db.get_value(doc.voucher_type, doc.voucher_no, "is_pos")
				if voucher_doc:
					frappe.logger().info(
						f"[POSAwesome] Skipping ERPNext bundle validation for POS invoice {doc.voucher_no} "
						f"(item: {doc.item_code}, warehouse: {doc.warehouse})"
					)
					return
			except Exception as e:
				# If we can't check is_pos, proceed with normal validation
				frappe.logger().warning(f"[POSAwesome] Error checking is_pos for bundle validation: {e}")
				pass

		# Call parent validation for non-POS invoices
		super().validate_qty(doc)


class CustomSalesInvoice(SalesInvoice):
	"""Custom Sales Invoice with auto batch splitting for POS-Awesome."""

	def onload(self):
		super().onload()
		self.fetch_batch_expiry_for_all_items()

	def validate(self):
		# Consolidated SI from POS merge: stock already updated on POS Invoice submit
		if cint(self.is_consolidated):
			self.update_stock = 0
		super().validate()
		self.fetch_batch_expiry_for_all_items()

	def before_validate(self):
		# Auto-split batches for POS-created invoices on submit
		if self._action == "submit" and self.is_pos:
			self.use_auto_batch_bundle_for_overdrawn_rows()

		super_before_validate = getattr(super(), "before_validate", None)
		if super_before_validate:
			super_before_validate()

	def before_submit(self):
		if cint(self.is_consolidated):
			self.update_stock = 0
		super().before_submit()

	def use_auto_batch_bundle_for_overdrawn_rows(self):
		"""Auto-split batches when selected batch has insufficient qty.
		
		This method follows the unicom_chemist approach:
		1. Detect if frontend has already split batches across multiple rows
		2. If yes, skip bundle creation - let ERPNext's standard flow handle it
		3. If no, only create bundles when selected batch has insufficient qty
		"""
		if self.is_return:
			return

		# First, identify which item/warehouse combinations have been split by frontend
		item_warehouse_batches = {}
		for row in self.items:
			if not should_auto_split_batch(row):
				continue
			
			warehouse = row.get("warehouse") or self.get("set_warehouse")
			if not warehouse:
				continue
				
			key = (row.item_code, warehouse)
			if key not in item_warehouse_batches:
				item_warehouse_batches[key] = set()
			item_warehouse_batches[key].add(row.get("batch_no"))
		
		# If any item/warehouse has multiple batches, frontend has already done the splitting
		# Skip bundle creation for ALL rows - let ERPNext's make_bundle_using_old_serial_batch_fields handle it
		frontend_split_items = {
			key for key, batches in item_warehouse_batches.items() 
			if len(batches) > 1
		}
		
		if frontend_split_items:
			frappe.log_error(
				title="Frontend Batch Split Detected",
				message=f"[BATCH DEBUG] Frontend has split batches for: {frontend_split_items}. "
						f"Skipping bundle creation - rows will keep batch_no field for ERPNext to process."
			)
			# Don't create bundles - let ERPNext's standard flow handle it
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
			
			# If selected batch has enough qty, skip bundle creation (unicom_chemist approach)
			# Let ERPNext's make_bundle_using_old_serial_batch_fields create the bundle
			if selected_batch_qty >= required_qty:
				consumed_in_doc[key] = already + required_qty
				continue

			# Selected batch insufficient - create bundle with auto-allocation across batches
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

	def fetch_batch_expiry_for_all_items(self):
		"""Fetch batch expiry dates for all items with serial_and_batch_bundle."""
		for item in self.items:
			if hasattr(item, 'serial_and_batch_bundle') and item.serial_and_batch_bundle:
				batch_expiry = self.get_batch_expiry_from_bundle(item.serial_and_batch_bundle)
				if batch_expiry and hasattr(item, 'custom_bundle_expiry_date'):
					item.custom_bundle_expiry_date = batch_expiry

	def get_batch_expiry_from_bundle(self, bundle_name):
		"""Get batch expiry date from Serial and Batch Bundle child table."""
		if not bundle_name:
			return None

		try:
			bundle_doc = frappe.get_doc("Serial and Batch Bundle", bundle_name)
			if hasattr(bundle_doc, 'entries') and bundle_doc.entries:
				first_entry = bundle_doc.entries[0]
				if hasattr(first_entry, 'custom_batch_expiry') and first_entry.custom_batch_expiry:
					return first_entry.custom_batch_expiry
			return None
		except Exception as e:
			frappe.log_error(f"Error fetching batch expiry from bundle {bundle_name}: {str(e)}")
			return None


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
	"""Create Serial & Batch Bundle with auto-allocated batches.
	
	This function is only called when a single row's selected batch is insufficient.
	It auto-allocates across multiple batches using FEFO logic.
	"""
	# If row has a specific batch assigned, try to use it first
	if row.get("batch_no"):
		batch_no = row.get("batch_no")
		available_qty = get_sbb_safe_batch_qty(row, batch_no)
		consumed = flt((consumed_by_batch or {}).get(batch_no, 0))
		net_available = max(0, available_qty - consumed)
		
		# If the assigned batch has enough quantity, use it exclusively
		if net_available >= required_qty:
			batches = frappe._dict({batch_no: required_qty})
		else:
			# Batch insufficient - auto-allocate across all available batches
			batches = get_batch_allocations(row, required_qty, consumed_by_batch=consumed_by_batch)
	else:
		# No batch assigned - auto-allocate across available batches
		batches = get_batch_allocations(row, required_qty, consumed_by_batch=consumed_by_batch)
	
	bundle = CustomSerialBatchCreation(
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


@frappe.whitelist()
def get_batch_expiry_from_bundle_api(bundle_name):
	"""Return the first batch expiry from a bundle the user can read."""
	if not bundle_name:
		frappe.throw("Bundle name is required")

	bundle_doc = frappe.get_doc("Serial and Batch Bundle", bundle_name)
	bundle_doc.check_permission("read")

	for entry in bundle_doc.get("entries", []):
		if entry.get("custom_batch_expiry"):
			return {"success": True, "expiry_date": entry.custom_batch_expiry}

	return {"success": False, "expiry_date": None}
