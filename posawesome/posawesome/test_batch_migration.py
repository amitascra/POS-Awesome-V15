#!/usr/bin/env python3
"""
Test script to verify batch migration from unicom_chemist to posawesome.
Run with: bench execute posawesome.test_batch_migration.test_overrides
"""
import frappe


def test_overrides():
	"""Test that POS-Awesome overrides are properly loaded."""
	print("\n" + "="*80)
	print("TESTING BATCH MIGRATION - DOCTYPE OVERRIDES")
	print("="*80 + "\n")
	
	# Test Sales Invoice override
	print("1. Testing Sales Invoice override...")
	try:
		from posawesome.posawesome.doctype_overrides.sales_invoice import CustomSalesInvoice
		print("   ✓ Sales Invoice override imported successfully")
		
		# Check if it has the required methods
		required_methods = [
			'use_auto_batch_bundle_for_overdrawn_rows',
			'fetch_batch_expiry_for_all_items',
			'get_batch_expiry_from_bundle'
		]
		for method in required_methods:
			if hasattr(CustomSalesInvoice, method):
				print(f"   ✓ Method '{method}' exists")
			else:
				print(f"   ✗ Method '{method}' MISSING")
	except Exception as e:
		print(f"   ✗ Sales Invoice override FAILED: {e}")
	
	# Test POS Invoice override
	print("\n2. Testing POS Invoice override...")
	try:
		from posawesome.posawesome.doctype_overrides.pos_invoice import CustomPOSInvoice
		print("   ✓ POS Invoice override imported successfully")
		
		# Check if it has the required methods
		required_methods = [
			'validate_pos_opening_entry',  # From original override
			'use_auto_batch_bundle_for_overdrawn_rows',  # From migration
		]
		for method in required_methods:
			if hasattr(CustomPOSInvoice, method):
				print(f"   ✓ Method '{method}' exists")
			else:
				print(f"   ✗ Method '{method}' MISSING")
	except Exception as e:
		print(f"   ✗ POS Invoice override FAILED: {e}")
	
	# Test Batch Allocation API
	print("\n3. Testing Batch Allocation API...")
	try:
		from posawesome.posawesome.api.pos_batch_allocation import (
			get_pos_batch_qty_allocation,
			validate_pos_batch_selections
		)
		print("   ✓ Batch allocation API imported successfully")
		print("   ✓ Function 'get_pos_batch_qty_allocation' exists")
		print("   ✓ Function 'validate_pos_batch_selections' exists")
	except Exception as e:
		print(f"   ✗ Batch allocation API FAILED: {e}")
	
	# Check hooks configuration
	print("\n4. Checking hooks configuration...")
	try:
		from posawesome.hooks import override_doctype_class
		
		if "Sales Invoice" in override_doctype_class:
			si_path = override_doctype_class["Sales Invoice"]
			print(f"   ✓ Sales Invoice override registered: {si_path}")
		else:
			print("   ✗ Sales Invoice override NOT registered in hooks")
		
		if "POS Invoice" in override_doctype_class:
			pi_path = override_doctype_class["POS Invoice"]
			print(f"   ✓ POS Invoice override registered: {pi_path}")
		else:
			print("   ✗ POS Invoice override NOT registered in hooks")
	except Exception as e:
		print(f"   ✗ Hooks check FAILED: {e}")
	
	# Check unicom_chemist hooks are disabled
	print("\n5. Checking unicom_chemist overrides are disabled...")
	try:
		from unicom_chemist.hooks import override_doctype_class as unicom_overrides
		
		if "Sales Invoice" in unicom_overrides:
			print("   ⚠ WARNING: Sales Invoice still registered in unicom_chemist")
		else:
			print("   ✓ Sales Invoice removed from unicom_chemist")
		
		if "POS Invoice" in unicom_overrides:
			print("   ⚠ WARNING: POS Invoice still registered in unicom_chemist")
		else:
			print("   ✓ POS Invoice removed from unicom_chemist")
		
		from unicom_chemist.hooks import page_js
		if page_js and "point-of-sale" in page_js:
			print("   ⚠ WARNING: pos_override.js still registered in unicom_chemist")
		else:
			print("   ✓ pos_override.js removed from unicom_chemist")
	except Exception as e:
		print(f"   ✗ Unicom hooks check FAILED: {e}")
	
	print("\n" + "="*80)
	print("TEST COMPLETE")
	print("="*80 + "\n")
	print("Next steps:")
	print("1. Run: bench restart")
	print("2. Run: bench --site pos-retail.worf.cloud clear-cache")
	print("3. Test POS with item MED-UCL-0021")
	print()


if __name__ == "__main__":
	test_overrides()
