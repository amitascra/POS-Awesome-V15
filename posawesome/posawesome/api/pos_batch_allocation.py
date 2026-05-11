"""
POS Batch Allocation API
Migrated from unicom_chemist for consolidated batch handling in POS-Awesome.
Provides robust batch allocation with ledger-based validation and hold tracking.
"""
import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.caching import redis_cache


def _as_list(value):
	if value is None:
		return []
	if isinstance(value, str):
		value = frappe.parse_json(value)
	if isinstance(value, list):
		return value
	return []


def _stock_qty(qty, conversion_factor):
	return flt(qty) * (flt(conversion_factor) or 1)


@frappe.whitelist()
def validate_pos_batch_selections(lines, company=None, posting_date=None):
	"""Validate POS batch selections before submit (prevents batch negative stock errors).

	Input `lines` is a list of dicts with:
	- item_code, warehouse, batch_no, qty, conversion_factor

	Returns a list of errors (empty when OK):
	[{item_code, warehouse, batch_no, required_stock_qty, available_stock_qty}]
	"""
	lines = _as_list(lines)

	# Group required stock qty by (item_code, warehouse, batch_no)
	required = {}
	for row in lines:
		if not isinstance(row, dict):
			continue
		item_code = row.get("item_code")
		warehouse = row.get("warehouse")
		batch_no = row.get("batch_no")
		if not item_code or not warehouse or not batch_no:
			continue
		qty = _stock_qty(row.get("qty"), row.get("conversion_factor"))
		if qty <= 0:
			continue
		key = (item_code, warehouse, batch_no)
		required[key] = flt(required.get(key, 0)) + qty

	if not required:
		return []

	# Validate permissions at least once per (item_code, warehouse)
	checked_item_wh = set()
	for item_code, warehouse, _batch_no in required.keys():
		k = (item_code, warehouse)
		if k in checked_item_wh:
			continue
		checked_item_wh.add(k)
		frappe.has_permission("Item", ptype="read", doc=item_code, throw=True)
		frappe.has_permission("Warehouse", ptype="read", doc=warehouse, throw=True)

	precision = frappe.get_precision("Stock Ledger Entry", "actual_qty")
	errors = []

	# Per (item_code, warehouse): get ledger net qty by batch
	for item_code, warehouse in checked_item_wh:
		net_by_batch = _batch_net_qty_by_batch_from_ledger(item_code, warehouse, precision)

		# Check all required batches for this item/warehouse
		for (ic, wh, bn), need in required.items():
			if ic != item_code or wh != warehouse:
				continue
			avail = flt(net_by_batch.get(bn, 0), precision)
			if avail + 1e-9 < flt(need, precision):
				errors.append(
					{
						"item_code": ic,
						"warehouse": wh,
						"batch_no": bn,
						"required_stock_qty": flt(need, precision),
						"available_stock_qty": max(0.0, avail),
					}
				)

	return errors


@redis_cache(ttl=60)  # Cache for 60 seconds - expensive query
def _batch_net_qty_by_batch_from_ledger(item_code, warehouse, precision):
	"""Per-batch net qty matching Serial and Batch Bundle validation.
	
	CACHED for 60 seconds to avoid repeated heavy SQL queries during POS operations.

	Includes:
	1) Serial and Batch Entry qty joined to SLE via bundle
	2) Legacy SLE rows with batch_no set and serial_and_batch_bundle IS NULL
	"""
	net_by_batch = {}

	# Bundle-based entries
	bundle_rows = frappe.db.sql(
		"""
		SELECT sbe.batch_no, SUM(sbe.qty) AS qty
		FROM `tabSerial and Batch Entry` sbe
		INNER JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sbe.parent
		INNER JOIN `tabStock Ledger Entry` sle ON sle.serial_and_batch_bundle = sbb.name
		WHERE sle.item_code = %(item_code)s
			AND sle.warehouse = %(warehouse)s
			AND sle.is_cancelled = 0
			AND sle.docstatus = 1
		GROUP BY sbe.batch_no
		""",
		{"item_code": item_code, "warehouse": warehouse},
		as_dict=True,
	)
	for row in bundle_rows:
		bn = row.batch_no
		if not bn:
			continue
		net_by_batch[bn] = flt(net_by_batch.get(bn, 0), precision) + flt(row.qty, precision)

	# Legacy SLE entries (without bundle)
	legacy_rows = frappe.db.sql(
		"""
		SELECT sle.batch_no, SUM(sle.actual_qty) AS qty
		FROM `tabStock Ledger Entry` sle
		WHERE sle.item_code = %(item_code)s
			AND sle.warehouse = %(warehouse)s
			AND sle.is_cancelled = 0
			AND sle.docstatus = 1
			AND sle.serial_and_batch_bundle IS NULL
			AND sle.batch_no IS NOT NULL
			AND sle.batch_no != ''
		GROUP BY sle.batch_no
		""",
		{"item_code": item_code, "warehouse": warehouse},
		as_dict=True,
	)
	for row in legacy_rows:
		bn = row.batch_no
		if not bn:
			continue
		net_by_batch[bn] = flt(net_by_batch.get(bn, 0), precision) + flt(row.qty, precision)

	return net_by_batch


def _merge_ledger_batches_into_availability(
	item_code, warehouse, avail_by_batch, order_batches, consumed_by_batch, precision
):
	"""Reconcile FIFO-style batch qty with SLE net per batch.

	Cap each FIFO batch using ledger net minus qty already committed on other cart lines.
	"""
	seen_order = list(order_batches)
	ledger_net_by_batch = _batch_net_qty_by_batch_from_ledger(item_code, warehouse, precision)

	# No ledger rows at all: do not wipe FIFO
	if not ledger_net_by_batch:
		return [bn for bn in seen_order if flt(avail_by_batch.get(bn, 0), precision) > 1e-9]

	for bn in list(avail_by_batch.keys()):
		ledger_net = flt(ledger_net_by_batch.get(bn, 0), precision)
		consumed = flt(consumed_by_batch.get(bn, 0), precision)
		net = max(0, ledger_net - consumed)
		if net <= 1e-9:
			avail_by_batch.pop(bn, None)
			if bn in seen_order:
				seen_order.remove(bn)
			continue
		prev = flt(avail_by_batch[bn], precision)
		avail_by_batch[bn] = min(prev, net)

	# Ledger shows positive batches not in FIFO list
	for bn, ledger_net in ledger_net_by_batch.items():
		if bn in avail_by_batch or bn in seen_order:
			continue
		consumed = flt(consumed_by_batch.get(bn, 0), precision)
		net = max(0, flt(ledger_net, precision) - consumed)
		if net <= 1e-9:
			continue
		avail_by_batch[bn] = net
		seen_order.append(bn)

	return [bn for bn in seen_order if flt(avail_by_batch.get(bn, 0), precision) > 1e-9]


def _cap_batch_qty_to_sellable_bin(avail_by_batch, order_batches, bin_avail, precision):
	"""Cap total batch qty to bin available qty."""
	sum_ab = flt(sum(avail_by_batch.values()), precision)
	excess = sum_ab - flt(bin_avail, precision)
	if excess <= 1e-9:
		return [bn for bn in order_batches if bn in avail_by_batch and avail_by_batch[bn] > 0]
	
	for bn in reversed(list(order_batches)):
		if excess <= 1e-9:
			break
		if bn not in avail_by_batch:
			continue
		cur = flt(avail_by_batch[bn], precision)
		if cur <= 0:
			continue
		red = min(excess, cur)
		cur = flt(cur - red, precision)
		excess = flt(excess - red, precision)
		if cur <= 1e-9:
			del avail_by_batch[bn]
		else:
			avail_by_batch[bn] = cur
	return [bn for bn in order_batches if bn in avail_by_batch and avail_by_batch[bn] > 0]


@frappe.whitelist()
def get_pos_batch_qty_allocation(
	item_code,
	warehouse,
	qty,
	conversion_factor=1,
	company=None,
	posting_date=None,
	prefer_batch_no=None,
	consumed_batches=None,
):
	"""POS: split qty across batches (stock UOM); prefer selected batch then Stock Settings order."""
	if not item_code or not warehouse:
		frappe.throw(_("Item Code and Warehouse are required"))

	frappe.has_permission("Item", ptype="read", doc=item_code, throw=True)
	frappe.has_permission("Warehouse", ptype="read", doc=warehouse, throw=True)

	cf = flt(conversion_factor) or 1
	qty = flt(qty)
	stock_qty_needed = qty * cf
	if stock_qty_needed <= 0:
		return []

	item = frappe.db.get_value(
		"Item", item_code, ["has_batch_no", "has_serial_no", "disabled"], as_dict=True
	)
	if not item or item.disabled:
		frappe.throw(_("Invalid Item"))
	if not item.has_batch_no or item.has_serial_no:
		frappe.throw(
			_("Multi-batch POS split applies only to batch items without serial numbers")
		)

	consumed_by_batch = {}
	if consumed_batches:
		if isinstance(consumed_batches, str):
			try:
				consumed_batches = frappe.parse_json(consumed_batches)
			except Exception:
				frappe.throw(_("Invalid batch data"), frappe.ValidationError)
		if not isinstance(consumed_batches, list):
			frappe.throw(_("Invalid batch data"), frappe.ValidationError)
		for row in consumed_batches:
			if not isinstance(row, dict):
				continue
			bn = row.get("batch_no")
			if not bn:
				continue
			consumed_by_batch[bn] = consumed_by_batch.get(bn, 0) + flt(row.get("qty"))

	based_on = (
		frappe.db.get_single_value("Stock Settings", "pick_serial_and_batch_based_on") or "FIFO"
	)
	kwargs = frappe._dict(
		item_code=item_code,
		warehouse=warehouse,
		company=company,
		based_on=based_on,
		qty=0,
		posting_date=posting_date or frappe.utils.today(),
	)
	from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import (
		get_auto_batch_nos,
	)

	available_batches = get_auto_batch_nos(kwargs)
	if not available_batches:
		frappe.throw(
			_("Item Code: {0} is not available under warehouse {1}.").format(
				frappe.bold(item_code), frappe.bold(warehouse)
			),
			title=_("Not Available"),
		)

	precision = frappe.get_precision("Stock Ledger Entry", "actual_qty")
	avail_by_batch = {}
	order_batches = []
	seen = set()
	for b in available_batches:
		bn = b.batch_no
		if bn in seen:
			continue
		seen.add(bn)
		raw = flt(b.qty, precision)
		consumed = flt(consumed_by_batch.get(bn, 0), precision)
		q = max(0, raw - consumed)
		if q > 0:
			order_batches.append(bn)
			avail_by_batch[bn] = q

	order_batches = _merge_ledger_batches_into_availability(
		item_code, warehouse, avail_by_batch, order_batches, consumed_by_batch, precision
	)

	from erpnext.accounts.doctype.pos_invoice.pos_invoice import get_bin_qty, get_pos_reserved_qty

	bin_qty = flt(get_bin_qty(item_code, warehouse), precision)
	pos_reserved = flt(get_pos_reserved_qty(item_code, warehouse), precision)
	bin_avail = flt(bin_qty - pos_reserved, precision)
	
	order_batches = _cap_batch_qty_to_sellable_bin(
		avail_by_batch, order_batches, bin_avail, precision
	)
	total_avail = flt(sum(avail_by_batch.values()), precision)

	if total_avail <= 0:
		frappe.throw(
			_("Item Code: {0} is not available under warehouse {1}.").format(
				frappe.bold(item_code), frappe.bold(warehouse)
			),
			title=_("Not Available"),
		)
	if stock_qty_needed > bin_avail + 1e-6:
		stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
		frappe.throw(
			_("Stock quantity not enough for Item Code: {0} under warehouse {1}. Available quantity {2} {3}.").format(
				frappe.bold(item_code),
				frappe.bold(warehouse),
				frappe.bold(flt(bin_avail, precision)),
				frappe.bold(stock_uom or ""),
			)
		)
	if total_avail + 1e-6 < stock_qty_needed:
		stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
		frappe.throw(
			_(
				"Stock quantity not enough for Item Code: {0} under warehouse {1}. Available quantity {2} {3}."
			).format(
				frappe.bold(item_code),
				frappe.bold(warehouse),
				frappe.bold(flt(total_avail, precision)),
				frappe.bold(stock_uom or ""),
			)
		)

	ordered_batches = []
	if prefer_batch_no and prefer_batch_no in avail_by_batch:
		ordered_batches.append(prefer_batch_no)
	for bn in order_batches:
		if bn not in ordered_batches:
			ordered_batches.append(bn)

	remaining = stock_qty_needed
	result = []
	for bn in ordered_batches:
		if remaining <= 1e-9:
			break
		a = avail_by_batch.get(bn, 0)
		if a <= 0:
			continue
		take = min(remaining, a)
		result.append({"batch_no": bn, "qty": flt(take, precision)})
		remaining -= take
	return result
