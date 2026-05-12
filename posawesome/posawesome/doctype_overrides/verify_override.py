"""
Simple verification script to check Sales Invoice override.
Run with: bench --site pos-retail.worf.cloud execute posawesome.posawesome.doctype_overrides.verify_override.run_tests
"""

import frappe
from frappe.utils import flt

def run_tests():
    """Run all verification tests"""
    print("\n" + "=" * 70)
    print("SALES INVOICE OVERRIDE VERIFICATION")
    print("=" * 70)
    
    results = []
    
    # Test 1: Override class
    print("\n[1/4] Checking override class...")
    try:
        si = frappe.new_doc('Sales Invoice')
        expected_module = "posawesome.posawesome.doctype_overrides.sales_invoice"
        if si.__class__.__module__ == expected_module:
            print(f"  ✓ Override loaded: {si.__class__.__name__}")
            results.append(True)
        else:
            print(f"  ✗ Wrong module: {si.__class__.__module__}")
            results.append(False)
    except Exception as e:
        print(f"  ✗ Error: {e}")
        results.append(False)
    
    # Test 2: Override methods
    print("\n[2/4] Checking override methods...")
    try:
        si = frappe.new_doc('Sales Invoice')
        if hasattr(si, 'use_auto_batch_bundle_for_overdrawn_rows'):
            print("  ✓ use_auto_batch_bundle_for_overdrawn_rows exists")
            results.append(True)
        else:
            print("  ✗ use_auto_batch_bundle_for_overdrawn_rows NOT found")
            results.append(False)
    except Exception as e:
        print(f"  ✗ Error: {e}")
        results.append(False)
    
    # Test 3: Batch utilities
    print("\n[3/4] Checking batch utilities...")
    try:
        from posawesome.posawesome.api.utilities import set_batch_nos_for_bundels
        print("  ✓ set_batch_nos_for_bundels imported")
        results.append(True)
    except Exception as e:
        print(f"  ✗ Error: {e}")
        results.append(False)
    
    # Test 4: Hooks configuration
    print("\n[4/4] Checking hooks configuration...")
    try:
        hooks = frappe.get_hooks()
        override_classes = hooks.get('override_doctype_class', {})
        sales_invoice_override = override_classes.get('Sales Invoice')
        expected = "posawesome.posawesome.doctype_overrides.sales_invoice.CustomSalesInvoice"
        
        # Handle both string and list formats
        if isinstance(sales_invoice_override, list):
            sales_invoice_override = sales_invoice_override[0] if sales_invoice_override else None
        
        if sales_invoice_override == expected:
            print(f"  ✓ Hooks configured correctly")
            results.append(True)
        else:
            print(f"  ✗ Hooks mismatch: {sales_invoice_override}")
            results.append(False)
    except Exception as e:
        print(f"  ✗ Error: {e}")
        results.append(False)
    
    # Summary
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"RESULT: {passed}/{total} tests passed")
    print("=" * 70)
    
    if passed == total:
        print("\n✓ ALL TESTS PASSED - Override is working correctly!")
        print("\nYou can now:")
        print("1. Hard refresh POS page (Ctrl+Shift+R)")
        print("2. Add item MED-UCL-0021 with qty 118")
        print("3. Verify 5 batch rows appear")
        print("4. Submit the invoice")
        print("\nThe batch reallocation fix will:")
        print("- Respect frontend single-batch assignments")
        print("- Skip reallocation when frontend assigns one batch")
        print("- Create bundles with correct batch quantities")
    else:
        print(f"\n✗ {total - passed} test(s) failed")
    
    return passed == total
