<template>
	<v-dialog v-model="dialogModel" max-width="900px" scrollable persistent>
		<v-card class="posa-item-details-dialog">
			<v-card-title class="d-flex align-center pa-4 bg-primary">
				<v-icon class="mr-2">mdi-package-variant</v-icon>
				<span class="text-h6">{{ __("Item Details") }}</span>
				<v-spacer></v-spacer>
				<v-btn icon variant="text" @click="closeDialog" size="small">
					<v-icon>mdi-close</v-icon>
				</v-btn>
			</v-card-title>

			<v-card-text class="pa-4" style="max-height: 70vh">
				<div v-if="item" class="posa-item-details-form">
					<!-- Item Header Info -->
					<v-card class="mb-4" variant="outlined">
						<v-card-text>
							<div class="text-h6 mb-2">{{ item.item_name }}</div>
							<div class="text-caption text-medium-emphasis">
								{{ __("Item Code") }}: {{ item.item_code }}
							</div>
						</v-card-text>
					</v-card>

					<!-- Basic Information Section -->
					<div class="posa-form-section mb-4">
						<div class="posa-section-header mb-3">
							<v-icon size="small" class="section-icon mr-2">mdi-information-outline</v-icon>
							<span class="posa-section-title font-weight-bold">{{
								__("Basic Information")
							}}</span>
						</div>
						<v-row dense>
							<v-col cols="12" md="4">
								<v-text-field
									density="comfortable"
									variant="outlined"
									color="primary"
									:label="frappe._('QTY')"
									hide-details
									:model-value="formatFloat(item.qty, hide_qty_decimals ? 0 : undefined)"
									@change="onQtyChange(item, $event)"
									:rules="[isNumber]"
									:disabled="!!item.posa_is_replace"
									prepend-inner-icon="mdi-numeric"
								></v-text-field>
								<div v-if="item.max_qty !== undefined" class="text-caption mt-1 ml-2">
									{{
										__("In stock: {0}", [
											formatFloat(item._base_actual_qty, hide_qty_decimals ? 0 : undefined),
										])
									}}
								</div>
							</v-col>
							<v-col cols="12" md="4">
								<v-select
									density="comfortable"
									:label="frappe._('UOM')"
									v-model="item.uom"
									:items="item.item_uoms"
									variant="outlined"
									item-title="uom"
									item-value="uom"
									hide-details
									@update:model-value="calcUom(item, $event)"
									:disabled="!!item.posa_is_replace || (isReturnInvoice && invoice_doc.return_against)"
									prepend-inner-icon="mdi-weight"
								></v-select>
							</v-col>
							<v-col cols="12" md="4">
								<v-text-field
									density="comfortable"
									variant="outlined"
									color="primary"
									:label="frappe._('Stock UOM')"
									hide-details
									v-model="item.stock_uom"
									disabled
									prepend-inner-icon="mdi-package"
								></v-text-field>
							</v-col>
						</v-row>
					</div>

					<!-- Pricing Section -->
					<div class="posa-form-section mb-4">
						<div class="posa-section-header mb-3">
							<v-icon size="small" class="section-icon mr-2">mdi-currency-usd</v-icon>
							<span class="posa-section-title font-weight-bold">{{
								__("Pricing & Discounts")
							}}</span>
						</div>
						<v-row dense>
							<v-col cols="12" md="4">
								<v-text-field
									density="comfortable"
									variant="outlined"
									color="primary"
									:label="frappe._('Rate')"
									hide-details
									:model-value="formatCurrency(item.rate)"
									@change="
										[
											setFormatedCurrency(item, 'rate', null, false, $event),
											calcPrices(item, $event.target.value, $event),
										]
									"
									:disabled="!pos_profile.posa_allow_user_to_edit_rate || !!item.posa_is_replace"
									prepend-inner-icon="mdi-currency-usd"
								></v-text-field>
							</v-col>
							<v-col cols="12" md="4">
								<v-text-field
									density="comfortable"
									variant="outlined"
									color="primary"
									:label="frappe._('Discount %')"
									hide-details
									:model-value="formatFloat(Math.abs(item.discount_percentage || 0))"
									@change="
										[
											setFormatedCurrency(item, 'discount_percentage', null, false, $event),
											calcPrices(item, $event.target.value, $event),
										]
									"
									:disabled="
										!pos_profile.posa_allow_user_to_edit_item_discount ||
										!!item.posa_is_replace ||
										!!item.posa_offer_applied
									"
									prepend-inner-icon="mdi-percent"
								></v-text-field>
							</v-col>
							<v-col cols="12" md="4">
								<v-text-field
									density="comfortable"
									variant="outlined"
									color="primary"
									:label="frappe._('Discount Amount')"
									hide-details
									:model-value="formatCurrency(Math.abs(item.discount_amount || 0))"
									@change="
										[
											setFormatedCurrency(item, 'discount_amount', null, false, $event),
											calcPrices(item, $event.target.value, $event),
										]
									"
									:disabled="
										!pos_profile.posa_allow_user_to_edit_item_discount ||
										!!item.posa_is_replace ||
										!!item.posa_offer_applied
									"
									prepend-inner-icon="mdi-tag-minus"
								></v-text-field>
							</v-col>
						</v-row>
						<v-row dense class="mt-2">
							<v-col cols="12" md="6">
								<v-text-field
									density="comfortable"
									variant="outlined"
									color="primary"
									:label="frappe._('Price List Rate')"
									hide-details
									:model-value="formatCurrency(item.price_list_rate)"
									disabled
									prepend-inner-icon="mdi-format-list-bulleted"
								></v-text-field>
							</v-col>
							<v-col cols="12" md="6">
								<v-text-field
									density="comfortable"
									variant="outlined"
									color="primary"
									:label="frappe._('Amount')"
									hide-details
									:model-value="formatCurrency(item.amount)"
									disabled
									prepend-inner-icon="mdi-cash"
								></v-text-field>
							</v-col>
						</v-row>
					</div>

					<!-- Serial Number Section -->
					<div
						class="posa-form-section mb-4"
						v-if="item.has_serial_no || item.serial_no || item.serial_no_data"
					>
						<div class="posa-section-header mb-3">
							<v-icon size="small" class="section-icon mr-2">mdi-barcode-scan</v-icon>
							<span class="posa-section-title font-weight-bold">{{
								__("Serial Number Information")
							}}</span>
						</div>
						<v-row dense>
							<v-col cols="12">
								<v-autocomplete
									v-model="item.serial_no_data"
									:items="getSerialOptions(item)"
									item-title="serial_no"
									variant="outlined"
									density="comfortable"
									color="primary"
									:label="frappe._('Serial No')"
									@update:model-value="setSerialNo(item)"
									hide-details
									multiple
									chips
									closable-chips
									prepend-inner-icon="mdi-barcode-scan"
								>
									<template v-slot:chip="{ props, item: chipItem }">
										<v-chip v-bind="props" :text="getRaw(chipItem).serial_no"></v-chip>
									</template>
									<template v-slot:item="{ props, item: listItem }">
										<v-list-item v-bind="props">
											<v-list-item-title v-html="getRaw(listItem).serial_no"></v-list-item-title>
										</v-list-item>
									</template>
								</v-autocomplete>
							</v-col>
						</v-row>
					</div>

					<!-- Batch Number Section -->
					<div class="posa-form-section mb-4" v-if="item.has_batch_no || item.batch_no">
						<div class="posa-section-header mb-3">
							<v-icon size="small" class="section-icon mr-2"
								>mdi-package-variant-closed</v-icon
							>
							<span class="posa-section-title font-weight-bold">{{
								__("Batch Information")
							}}</span>
						</div>
						<v-row dense>
							<v-col cols="12" md="4">
								<v-text-field
									density="comfortable"
									variant="outlined"
									color="primary"
									:label="frappe._('Batch No. Available QTY')"
									hide-details
									:model-value="formatFloat(item.actual_batch_qty)"
									disabled
									prepend-inner-icon="mdi-package-variant"
								></v-text-field>
							</v-col>
							<v-col cols="12" md="4">
								<v-text-field
									density="comfortable"
									variant="outlined"
									color="primary"
									:label="frappe._('Batch No Expiry Date')"
									hide-details
									v-model="item.batch_no_expiry_date"
									disabled
									prepend-inner-icon="mdi-calendar-clock"
								></v-text-field>
							</v-col>
							<v-col cols="12" md="4">
								<v-autocomplete
									v-model="item.batch_no"
									:items="getBatchOptions(item)"
									item-title="batch_no"
									variant="outlined"
									density="comfortable"
									color="primary"
									:label="frappe._('Batch No')"
									@update:model-value="setBatchQty(item, $event)"
									hide-details
									prepend-inner-icon="mdi-package-variant-closed"
								>
									<template v-slot:item="{ props, item: batchItem }">
										<v-list-item v-bind="props">
											<v-list-item-title
												v-html="getRaw(batchItem).batch_no"
											></v-list-item-title>
											<v-list-item-subtitle class="d-flex align-center">
												<span
													v-html="
														`Available QTY  '${
															getRaw(batchItem).available_qty ??
															getRaw(batchItem).batch_qty
														}' - Expiry Date ${getRaw(batchItem).expiry_date}`
													"
												></span>
												<v-chip
													v-if="getRaw(batchItem).is_expired"
													color="error"
													size="x-small"
													variant="flat"
													class="ml-2"
												>
													{{ __("Expired") }}
												</v-chip>
											</v-list-item-subtitle>
										</v-list-item>
									</template>
								</v-autocomplete>
							</v-col>
						</v-row>
					</div>

					<!-- Delivery Date Section -->
					<div
						class="posa-form-section mb-4"
						v-if="
							pos_profile.posa_allow_sales_order &&
							['Order', 'Quotation'].includes(invoiceType || '')
						"
					>
						<div class="posa-section-header mb-3">
							<v-icon size="small" class="section-icon mr-2">mdi-calendar-check</v-icon>
							<span class="posa-section-title font-weight-bold">{{
								__("Delivery Information")
							}}</span>
						</div>
						<v-row dense>
							<v-col cols="12" md="6">
								<VueDatePicker
									v-model="item.posa_delivery_date"
									model-type="format"
									format="dd-MM-yyyy"
									:min-date="new Date()"
									auto-apply
									@update:model-value="validateDueDate(item)"
								/>
							</v-col>
						</v-row>
					</div>

					<!-- Notes Section -->
					<div class="posa-form-section mb-4" v-if="pos_profile.posa_display_additional_notes">
						<div class="posa-section-header mb-3">
							<v-icon size="small" class="section-icon mr-2">mdi-note-text</v-icon>
							<span class="posa-section-title font-weight-bold">{{ __("Notes") }}</span>
						</div>
						<v-row dense>
							<v-col cols="12">
								<v-textarea
									v-model="item.posa_notes"
									variant="outlined"
									:label="frappe._('Item Notes')"
									rows="3"
									hide-details
									prepend-inner-icon="mdi-note-text-outline"
								></v-textarea>
							</v-col>
						</v-row>
					</div>
				</div>
			</v-card-text>

			<v-divider></v-divider>

			<v-card-actions class="pa-4">
				<v-spacer></v-spacer>
				<v-btn variant="text" @click="closeDialog">{{ __("Close") }}</v-btn>
				<v-btn color="primary" variant="elevated" @click="closeDialog">
					{{ __("Done") }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { getDisplayableBatchOptions } from "../../../composables/pos/shared/useBatchSerial";
import type { CartItem, POSProfile, InvoiceDoc } from "../../../types/models";

interface Props {
	modelValue: boolean;
	item: CartItem | any;
	pos_profile: POSProfile | any;
	invoiceType?: string;
	isReturnInvoice?: boolean;
	invoice_doc?: InvoiceDoc | any;
	hide_qty_decimals: boolean;

	// Formatters
	formatFloat: (_val: any, _precision?: number) => string;
	formatCurrency: (_val: any, _precision?: number) => string;
	currencySymbol: (_currency?: string) => string;
	isNumber: (_val: any) => boolean | string;

	// Actions
	setFormatedCurrency: (_item: any, _field: string, _value: any, _force?: boolean, _event?: any) => void;
	calcPrices: (_item: any, _value: any, _event?: any) => void;
	calcUom: (_item: any, _uom: string) => void;
	changePriceListRate: (_item: any) => void;
	getSerialOptions: (_item: any) => any[];
	setSerialNo: (_item: any) => void;
	setBatchQty: (_item: any, _event: any) => void;
	validateDueDate: (_item: any) => void;
}

const props = defineProps<Props>();

const emit = defineEmits<{
	"update:modelValue": [value: boolean];
	"qty-change": [item: CartItem, event: any];
}>();

const dialogModel = computed({
	get: () => props.modelValue,
	set: (value) => emit("update:modelValue", value),
});

const __ = (window as any).__ || ((s: string) => s);
const frappe = (window as any).frappe || { _: (s: string) => s };

const onQtyChange = (item: CartItem, event: any) => {
	emit("qty-change", item, event);
};

const closeDialog = () => {
	emit("update:modelValue", false);
};

const getRaw = (item: any) => item?.raw || {};
const getBatchOptions = (item: any) => getDisplayableBatchOptions(item?.batch_no_data);
</script>

<style scoped>
.posa-item-details-dialog {
	border-radius: 8px;
}

.posa-section-header {
	display: flex;
	align-items: center;
	margin-bottom: 12px;
}

.section-icon {
	opacity: 0.7;
}

.posa-section-title {
	font-size: 1rem;
}
</style>
