# -*- coding: utf-8 -*-
# Copyright (c) 2020, Youssef Restom and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.utils import flt
from erpnext.stock.doctype.batch.batch import get_batch_qty


@frappe.whitelist()
def get_batch_info(item_code, warehouse):
	"""
	Get batch information for an item in a specific warehouse.
	Returns all batches with their stock levels, expiry dates, and other details.
	"""
	if not item_code:
		frappe.throw("Item Code is required")
	
	if not warehouse:
		frappe.throw("Warehouse is required. Please ensure your POS Profile has a warehouse configured.")

	# Check if item has batches
	has_batch_no = frappe.db.get_value("Item", item_code, "has_batch_no")
	
	# Return early for non-batch-tracked items with appropriate flag
	if not has_batch_no:
		return {
			"is_batch_tracked": False,
			"batches": [],
			"bundle_info": None,
		}

	# Get all batches for this item from Serial and Batch Entry
	batches_data = frappe.db.sql(
		"""
		SELECT DISTINCT
			sbe.batch_no,
			b.expiry_date,
			SUM(sbe.qty) as available_qty
		FROM `tabSerial and Batch Entry` sbe
		JOIN `tabSerial and Batch Bundle` sabb ON sbe.parent = sabb.name
		JOIN `tabBatch` b ON sbe.batch_no = b.name
		JOIN `tabStock Ledger Entry` sle ON sabb.name = sle.serial_and_batch_bundle
		WHERE sle.item_code = %s
		AND sle.warehouse = %s
		AND sle.is_cancelled = 0
		AND b.disabled = 0
		AND sbe.batch_no IS NOT NULL
		GROUP BY sbe.batch_no, b.expiry_date
		ORDER BY b.expiry_date ASC, sbe.batch_no ASC
		""",
		(item_code, warehouse),
		as_dict=True,
	)

	# Format batch data
	batches = []
	for batch_data in batches_data:
		batch_no = batch_data.get("batch_no")
		if batch_no:
			batches.append({
				"batch_no": batch_no,
				"expiry_date": batch_data.get("expiry_date"),
				"available_qty": flt(batch_data.get("available_qty", 0)),
			})

	# Get Serial and Batch Bundle info if available
	bundle_info = None
	bundle_records = frappe.db.sql(
		"""
		SELECT DISTINCT sle.serial_and_batch_bundle
		FROM `tabStock Ledger Entry` sle
		WHERE sle.item_code = %s
		AND sle.warehouse = %s
		AND sle.is_cancelled = 0
		AND sle.serial_and_batch_bundle IS NOT NULL
		LIMIT 1
		""",
		(item_code, warehouse),
		as_dict=True,
	)

	if bundle_records and bundle_records[0].get("serial_and_batch_bundle"):
		bundle_name = bundle_records[0].get("serial_and_batch_bundle")
		try:
			bundle_doc = frappe.get_doc("Serial and Batch Bundle", bundle_name)
			bundle_info = {
				"name": bundle_doc.name,
				"docstatus": bundle_doc.docstatus,
				"total_entries": len(bundle_doc.entries) if hasattr(bundle_doc, 'entries') else 0,
				"creation": str(bundle_doc.creation) if hasattr(bundle_doc, 'creation') else None,
			}
		except Exception:
			pass

	return {
		"is_batch_tracked": True,
		"batches": batches,
		"bundle_info": bundle_info,
	}
