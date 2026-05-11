# Batch Handling Migration: Unicom → POS-Awesome

## Overview
Consolidated batch splitting logic from `unicom_chemist` app into `posawesome` to eliminate conflicts and improve maintainability.

## What Was Migrated

### 1. Backend Batch Allocation API
**Source:** `unicom_chemist/unicom_chemist/api/pos_batch_allocation.py`
**Destination:** `posawesome/posawesome/api/pos_batch_allocation.py`

Features:
- `get_pos_batch_qty_allocation()` - Smart batch allocation using FIFO/FEFO
- `validate_pos_batch_selections()` - Pre-submit validation
- Ledger-based stock calculation (includes SBB + legacy SLE)
- Handles consumed batches across cart lines

### 2. Sales Invoice Override
**Source:** `unicom_chemist/unicom_chemist/sales_invoice.py`
**Destination:** `posawesome/posawesome/doctype_overrides/sales_invoice.py`

Features:
- Auto-splits batches for POS-created Sales Invoices
- Handles consolidated invoices (prevents double stock posting)
- Fetches batch expiry dates from bundles
- Creates Serial & Batch Bundles automatically

### 3. POS Invoice Override
**Source:** `unicom_chemist/pos_invoice.py` + existing `posawesome/overrides/pos_invoice.py`
**Destination:** `posawesome/posawesome/doctype_overrides/pos_invoice.py`

Features:
- POS Awesome shift validation (preserved from existing override)
- Auto-splits batches when selected batch has insufficient qty
- Creates Serial & Batch Bundles automatically
- Tracks consumption across multiple cart rows
- Prevents over-allocation within same invoice

## Changes Made

### POS-Awesome (`posawesome/hooks.py`)
```python
override_doctype_class = {
    "Sales Invoice": "posawesome.posawesome.doctype_overrides.sales_invoice.CustomSalesInvoice",
    "POS Invoice": "posawesome.posawesome.doctype_overrides.pos_invoice.CustomPOSInvoice",
    ...
}
```

### Unicom Chemist (`unicom_chemist/hooks.py`)
```python
# Disabled Sales Invoice and POS Invoice overrides (moved to POS-Awesome)
override_doctype_class = {
    # "Sales Invoice": Moved to POS-Awesome app
    # "POS Invoice": Moved to POS-Awesome app
    ...
}

# Disabled pos_override.js (moved to POS-Awesome)
# page_js = {
#     "point-of-sale": "public/js/pos_override.js"
# }
```

## Benefits

1. **No More Conflicts** - Single source of truth for batch handling
2. **Better Integration** - Batch logic lives with POS frontend
3. **Easier Debugging** - All batch code in one app
4. **Cleaner Separation** - Unicom app focuses on business logic, not POS mechanics

## Testing Checklist

- [ ] Restart bench: `bench restart`
- [ ] Clear cache: `bench --site [site] clear-cache`
- [ ] Test batch splitting with item MED-UCL-0021
- [ ] Verify correct available qty (170 units)
- [ ] Test invoice submission without BatchNegativeStockError
- [ ] Verify batch split warning dialog appears
- [ ] Test multi-batch allocation

## Rollback Plan

If issues occur, re-enable unicom_chemist overrides:

1. Uncomment in `unicom_chemist/hooks.py`:
   ```python
   override_doctype_class = {
       "POS Invoice": "unicom_chemist.pos_invoice.CustomPOSInvoice",
   }
   page_js = {
       "point-of-sale": "public/js/pos_override.js"
   }
   ```

2. Comment out in `posawesome/hooks.py`:
   ```python
   override_doctype_class = {
       # "POS Invoice": "posawesome.posawesome.doctype_overrides.pos_invoice.CustomPOSInvoice",
   }
   ```

3. Restart: `bench restart`

## Next Steps

1. Migrate frontend batch UI from `pos_override.js` to POS-Awesome Vue components
2. Add batch hold/reservation tracking to POS-Awesome
3. Remove deprecated `unicom_chemist/public/js/pos_override.js` after full migration
4. Update documentation

## Notes

- The `get_live_batch_qty` API in POS-Awesome now works alongside the migrated batch allocation
- Frontend warehouse path fix (`context.pos_profile.warehouse`) is still active
- Backend auto-splitting happens during `before_validate` on submit
