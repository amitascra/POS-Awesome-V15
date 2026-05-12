#!/usr/bin/env python3
"""
Test script to verify Sales Invoice override and batch allocation logic.
Run this from the doctype_overrides directory to test the override functionality.
"""

import sys
import os

# Add frappe-bench to path
sys.path.insert(0, '/home/ubuntu/frappe-bench')
os.chdir('/home/ubuntu/frappe-bench')

import frappe
from frappe.utils import flt

def test_override_loaded():
    """Test 1: Verify Sales Invoice override class is loaded"""
    print("\n" + "=" * 70)
    print("TEST 1: Verify Sales Invoice Override Class")
    print("=" * 70)
    
    try:
        frappe.init(site='pos-retail.worf.cloud')
        frappe.connect()
        frappe.set_user('Administrator')
        
        # Create a new Sales Invoice instance
        si = frappe.get_doc('Sales Invoice')
        
        print(f"✓ Sales Invoice class: {si.__class__.__name__}")
        print(f"✓ Sales Invoice module: {si.__class__.__module__}")
        
        # Check if it's the custom class
        expected_module = "posawesome.posawesome.doctype_overrides.sales_invoice"
        if si.__class__.__module__ == expected_module:
            print(f"✓ SUCCESS: Override is correctly loaded from {expected_module}")
            return True
        else:
            print(f"✗ FAIL: Override NOT loaded. Expected: {expected_module}")
            print(f"  Got: {si.__class__.__module__}")
            return False
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        frappe.destroy()

def test_override_methods():
    """Test 2: Verify override methods exist"""
    print("\n" + "=" * 70)
    print("TEST 2: Verify Override Methods Exist")
    print("=" * 70)
    
    try:
        frappe.init(site='pos-retail.worf.cloud')
        frappe.connect()
        frappe.set_user('Administrator')
        
        si = frappe.get_doc('Sales Invoice')
        
        # Check for custom methods
        methods_to_check = [
            'use_auto_batch_bundle_for_overdrawn_rows',
            'validate',
        ]
        
        all_exist = True
        for method in methods_to_check:
            if hasattr(si, method):
                print(f"✓ Method '{method}' exists")
            else:
                print(f"✗ Method '{method}' NOT found")
                all_exist = False
        
        return all_exist
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        frappe.destroy()

def test_batch_utilities():
    """Test 3: Verify batch utility functions"""
    print("\n" + "=" * 70)
    print("TEST 3: Verify Batch Utility Functions")
    print("=" * 70)
    
    try:
        frappe.init(site='pos-retail.worf.cloud')
        frappe.connect()
        frappe.set_user('Administrator')
        
        from posawesome.posawesome.api.utilities import set_batch_nos_for_bundels
        print("✓ set_batch_nos_for_bundels imported successfully")
        
        # Check function signature
        import inspect
        sig = inspect.signature(set_batch_nos_for_bundels)
        print(f"✓ Function signature: {sig}")
        
        # Check docstring
        if set_batch_nos_for_bundels.__doc__:
            print(f"✓ Function has docstring")
            print(f"  First line: {set_batch_nos_for_bundels.__doc__.split(chr(10))[0]}")
        
        return True
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        frappe.destroy()

def test_hooks_configuration():
    """Test 4: Verify hooks configuration"""
    print("\n" + "=" * 70)
    print("TEST 4: Verify Hooks Configuration")
    print("=" * 70)
    
    try:
        frappe.init(site='pos-retail.worf.cloud')
        frappe.connect()
        frappe.set_user('Administrator')
        
        hooks = frappe.get_hooks()
        
        # Check override_doctype_class
        override_classes = hooks.get('override_doctype_class', {})
        sales_invoice_override = override_classes.get('Sales Invoice')
        
        if sales_invoice_override:
            print(f"✓ Sales Invoice override configured: {sales_invoice_override}")
            expected = "posawesome.posawesome.doctype_overrides.sales_invoice.CustomSalesInvoice"
            if sales_invoice_override == expected:
                print(f"✓ Override path is correct")
                return True
            else:
                print(f"✗ Override path mismatch. Expected: {expected}")
                return False
        else:
            print("✗ Sales Invoice override NOT configured in hooks")
            return False
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        frappe.destroy()

def test_batch_reallocation_logic():
    """Test 5: Verify batch reallocation logic fix"""
    print("\n" + "=" * 70)
    print("TEST 5: Verify Batch Reallocation Logic Fix")
    print("=" * 70)
    
    try:
        # Read the utilities.py file to check for the fix
        utilities_path = "/home/ubuntu/frappe-bench/apps/posawesome/posawesome/posawesome/api/utilities.py"
        
        with open(utilities_path, 'r') as f:
            content = f.read()
        
        # Check for key fix elements
        checks = [
            ("frontend_batches = set", "Frontend batch detection"),
            ("len(frontend_batches) == 1", "Single batch check"),
            ("Respecting frontend choice", "Skip reallocation logic"),
            ("reallocated.discard", "Remove from reallocated set"),
        ]
        
        all_present = True
        for check_str, description in checks:
            if check_str in content:
                print(f"✓ {description}: Found")
            else:
                print(f"✗ {description}: NOT found")
                all_present = False
        
        return all_present
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("SALES INVOICE OVERRIDE & BATCH ALLOCATION TEST SUITE")
    print("=" * 70)
    
    results = []
    
    # Run all tests
    results.append(("Override Class Loaded", test_override_loaded()))
    results.append(("Override Methods Exist", test_override_methods()))
    results.append(("Batch Utilities Available", test_batch_utilities()))
    results.append(("Hooks Configuration", test_hooks_configuration()))
    results.append(("Batch Reallocation Logic", test_batch_reallocation_logic()))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print("=" * 70)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 70)
    
    if passed == total:
        print("\n✓ ALL TESTS PASSED! Override is working correctly.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. Please review the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
