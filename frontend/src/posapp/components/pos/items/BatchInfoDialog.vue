<template>
	<v-dialog v-model="isOpen" max-width="900px" scrollable>
		<v-card class="batch-info-dialog">
			<v-card-title class="d-flex align-center justify-space-between">
				<div>
					<div class="text-h6">{{ __("Batch Information") }}</div>
					<div class="text-caption text-secondary">{{ localItemCode || props.itemCode }} - {{ localItemName || props.itemName }}</div>
				</div>
				<v-btn icon size="small" variant="text" @click="isOpen = false">
					<v-icon>mdi-close</v-icon>
				</v-btn>
			</v-card-title>

			<v-divider></v-divider>

			<v-card-text class="pa-6">
				<div v-if="loading" class="d-flex justify-center align-center" style="min-height: 300px">
					<v-progress-circular indeterminate color="primary"></v-progress-circular>
				</div>

				<div v-else-if="!isItemBatchTracked" class="text-center py-12">
					<v-icon size="64" class="text-warning mb-4">mdi-information-outline</v-icon>
					<div class="text-h6 mb-2">{{ __("Non-Batch Tracked Item") }}</div>
					<div class="text-body2 text-secondary">
						{{ __("This item does not require batch tracking.") }}
					</div>
					<div class="text-caption text-secondary mt-4">
						{{ __("Batch information is only available for items that require batch tracking.") }}
					</div>
				</div>

				<div v-else-if="batches.length === 0" class="text-center py-8">
					<v-icon size="48" class="text-secondary mb-4">mdi-information-outline</v-icon>
					<div class="text-body2 text-secondary">{{ __("No batch information available for this item") }}</div>
				</div>

				<div v-else>
					<!-- Summary Section -->
					<div class="batch-summary mb-6">
						<v-row>
							<v-col cols="12" sm="6">
								<div class="summary-card">
									<div class="summary-label">{{ __("Total Batches") }}</div>
									<div class="summary-value">{{ batches.length }}</div>
								</div>
							</v-col>
							<v-col cols="12" sm="6">
								<div class="summary-card">
									<div class="summary-label">{{ __("Total Stock") }}</div>
									<div class="summary-value">{{ totalStock }}</div>
								</div>
							</v-col>
						</v-row>
					</div>

					<!-- Batches Table -->
					<div class="batches-table-wrapper">
						<v-table density="compact" class="batches-table">
							<thead>
								<tr>
									<th class="text-left">{{ __("Batch No") }}</th>
									<th class="text-right">{{ __("Available Qty") }}</th>
									<th class="text-center">{{ __("Expiry Date") }}</th>
									<th class="text-center">{{ __("Status") }}</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="batch in batches" :key="batch.batch_no" :class="getBatchRowClass(batch)">
									<td class="text-left font-weight-medium">
										{{ batch.batch_no }}
									</td>
									<td class="text-right">
										<span :class="{ 'text-error': batch.available_qty <= 0 }">
											{{ formatNumber(batch.available_qty) }}
										</span>
									</td>
									<td class="text-center">
										<span v-if="batch.expiry_date" :class="getExpiryClass(batch.expiry_date)">
											{{ formatDate(batch.expiry_date) }}
										</span>
										<span v-else class="text-secondary">{{ __("N/A") }}</span>
									</td>
									<td class="text-center">
										<v-chip
											:color="getBatchStatusColor(batch)"
											size="small"
										>
											{{ getBatchStatus(batch) }}
										</v-chip>
									</td>
								</tr>
							</tbody>
						</v-table>
					</div>

					<!-- Serial and Batch Bundle Info (if applicable) -->
					<div v-if="bundleInfo" class="mt-6 pt-6 border-top">
						<div class="d-flex align-center justify-space-between mb-4">
							<div class="text-subtitle2">{{ __("Serial & Batch Bundle Details") }}</div>
							<v-btn
								size="small"
								variant="outlined"
								color="primary"
								@click="showBundleDetails = true"
							>
								{{ __("View Full Details") }}
							</v-btn>
						</div>
						<v-row>
							<v-col cols="12" sm="6">
								<div class="info-item">
									<span class="info-label">{{ __("Bundle ID") }}:</span>
									<span class="info-value font-monospace">{{ bundleInfo.name }}</span>
								</div>
							</v-col>
							<v-col cols="12" sm="6">
								<div class="info-item">
									<span class="info-label">{{ __("Status") }}:</span>
									<v-chip
										:color="bundleInfo.docstatus === 1 ? 'success' : 'warning'"
										size="small"
										variant="tonal"
									>
										{{ bundleInfo.docstatus === 1 ? __("Submitted") : __("Draft") }}
									</v-chip>
								</div>
							</v-col>
							<v-col cols="12" sm="6">
								<div class="info-item">
									<span class="info-label">{{ __("Total Entries") }}:</span>
									<span class="info-value">{{ bundleInfo.total_entries || 0 }}</span>
								</div>
							</v-col>
							<v-col cols="12" sm="6">
								<div class="info-item">
									<span class="info-label">{{ __("Created On") }}:</span>
									<span class="info-value">{{ formatDate(bundleInfo.creation) }}</span>
								</div>
							</v-col>
						</v-row>
					</div>
				</div>
			</v-card-text>

			<v-divider></v-divider>

			<v-card-actions class="pa-4">
				<v-spacer></v-spacer>
				<v-btn variant="text" @click="isOpen = false">
					{{ __("Close") }}
				</v-btn>
			</v-card-actions>
		</v-card>

		<!-- Bundle Details Dialog -->
		<v-dialog v-model="showBundleDetails" max-width="600px" scrollable>
			<v-card class="bundle-details-dialog">
				<v-card-title class="d-flex align-center pa-4 bg-primary">
					<v-icon class="mr-2">mdi-package-variant-closed</v-icon>
					<span class="text-h6">{{ __("Serial & Batch Bundle Details") }}</span>
					<v-spacer></v-spacer>
					<v-btn icon variant="text" @click="showBundleDetails = false" size="small">
						<v-icon>mdi-close</v-icon>
					</v-btn>
				</v-card-title>

				<v-card-text class="pa-4">
					<v-alert v-if="bundleInfo" type="info" variant="tonal" class="mb-4">
						<div class="text-subtitle2 mb-2">{{ __("Bundle Information") }}</div>
						<div class="info-item">
							<span class="info-label">{{ __("Bundle ID") }}:</span>
							<span class="info-value font-monospace">{{ bundleInfo.name }}</span>
						</div>
						<div class="info-item">
							<span class="info-label">{{ __("Status") }}:</span>
							<v-chip
								:color="bundleInfo.docstatus === 1 ? 'success' : 'warning'"
								size="small"
								variant="tonal"
							>
								{{ bundleInfo.docstatus === 1 ? __("Submitted") : __("Draft") }}
							</v-chip>
						</div>
						<div class="info-item">
							<span class="info-label">{{ __("Total Entries") }}:</span>
							<span class="info-value">{{ bundleInfo.total_entries || 0 }}</span>
						</div>
						<div class="info-item">
							<span class="info-label">{{ __("Created On") }}:</span>
							<span class="info-value">{{ formatDate(bundleInfo.creation) }}</span>
						</div>
					</v-alert>
					<div v-else class="text-center py-8 text-secondary">
						<v-icon size="48" class="mb-4">mdi-information-outline</v-icon>
						<div>{{ __("No bundle information available") }}</div>
					</div>
				</v-card-text>

				<v-card-actions class="pa-4">
					<v-spacer></v-spacer>
					<v-btn variant="text" @click="showBundleDetails = false">
						{{ __("Close") }}
					</v-btn>
				</v-card-actions>
			</v-card>
		</v-dialog>
	</v-dialog>
</template>

<script setup>
import { ref, computed } from "vue";

const props = defineProps({
	itemCode: {
		type: String,
		default: '',
	},
	itemName: {
		type: String,
		default: '',
	},
	warehouse: {
		type: String,
		default: '',
	},
});

const isOpen = ref(false);
const loading = ref(false);
const batches = ref([]);
const bundleInfo = ref(null);
const localItemCode = ref('');
const localItemName = ref('');
const localWarehouse = ref('');
const showBundleDetails = ref(false);

const totalStock = computed(() => {
	return batches.value.reduce((sum, batch) => sum + (batch.available_qty || 0), 0);
});

const isBatchTracked = ref(true);

// Computed property to check if item is batch tracked
const isItemBatchTracked = computed(() => {
	return isBatchTracked.value;
});

const formatNumber = (value) => {
	if (!value) return "0";
	return parseFloat(value).toFixed(2);
};

const formatDate = (dateStr) => {
	if (!dateStr) return "";
	try {
		const date = new Date(dateStr);
		return date.toLocaleDateString();
	} catch {
		return dateStr;
	}
};

const isExpired = (expiryDate) => {
	if (!expiryDate) return false;
	return new Date(expiryDate) < new Date();
};

const isExpiringSoon = (expiryDate) => {
	if (!expiryDate) return false;
	const today = new Date();
	const expiry = new Date(expiryDate);
	const daysUntilExpiry = Math.floor((expiry - today) / (1000 * 60 * 60 * 24));
	return daysUntilExpiry >= 0 && daysUntilExpiry <= 30;
};

const getExpiryClass = (expiryDate) => {
	if (isExpired(expiryDate)) return "text-error font-weight-bold";
	if (isExpiringSoon(expiryDate)) return "text-warning font-weight-bold";
	return "text-success";
};

const getBatchStatus = (batch) => {
	if (batch.available_qty <= 0) return __("Out of Stock");
	if (isExpired(batch.expiry_date)) return __("Expired");
	if (isExpiringSoon(batch.expiry_date)) return __("Expiring Soon");
	return __("Available");
};

const getBatchStatusColor = (batch) => {
	if (batch.available_qty <= 0) return "error";
	if (isExpired(batch.expiry_date)) return "error";
	if (isExpiringSoon(batch.expiry_date)) return "warning";
	return "success";
};

const getBatchRowClass = (batch) => {
	if (batch.available_qty <= 0) return "opacity-50";
	if (isExpired(batch.expiry_date)) return "opacity-50";
	return "";
};

const fetchBatchInfo = async () => {
	loading.value = true;
	try {
		const itemCodeToUse = localItemCode.value || props.itemCode;
		const warehouseToUse = localWarehouse.value || props.warehouse;
		
		console.log("[BatchInfo] Fetching with itemCode:", itemCodeToUse, "warehouse:", warehouseToUse);
		
		const response = await frappe.call({
			method: "posawesome.posawesome.api.batch_info.get_batch_info",
			args: {
				item_code: itemCodeToUse,
				warehouse: warehouseToUse,
			},
		});

		if (response.message) {
			isBatchTracked.value = response.message.is_batch_tracked || false;
			batches.value = response.message.batches || [];
			bundleInfo.value = response.message.bundle_info || null;
		}
	} catch (error) {
		console.error("Error fetching batch info:", error);
		frappe.msgprint({
			title: __("Error"),
			message: __("Failed to fetch batch information"),
			indicator: "red",
		});
	} finally {
		loading.value = false;
	}
};

const open = (itemCode, itemName, warehouse) => {
	// Reset state before opening
	batches.value = [];
	bundleInfo.value = null;
	isBatchTracked.value = true;
	loading.value = false;
	
	// Set local values from arguments or props
	localItemCode.value = itemCode || props.itemCode;
	localItemName.value = itemName || props.itemName;
	localWarehouse.value = warehouse || props.warehouse;
	
	console.log("[BatchInfo] Opening with - itemCode:", localItemCode.value, "itemName:", localItemName.value, "warehouse:", localWarehouse.value);
	
	// Open dialog
	isOpen.value = true;
	
	// Fetch fresh data
	fetchBatchInfo();
};

const close = () => {
	isOpen.value = false;
};

defineExpose({ open, close, isOpen });
</script>

<style scoped>
.batch-info-dialog {
	background: var(--pos-surface-raised);
	color: var(--pos-text-primary);
}

.batch-summary {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
	gap: 16px;
}

.summary-card {
	padding: 16px;
	background: rgba(var(--v-theme-primary), 0.08);
	border-radius: 8px;
	border-left: 4px solid var(--v-theme-primary);
}

.summary-label {
	font-size: 0.875rem;
	color: var(--pos-text-secondary);
	margin-bottom: 8px;
	font-weight: 500;
}

.summary-value {
	font-size: 1.5rem;
	font-weight: 700;
	color: var(--v-theme-primary);
}

.batches-table-wrapper {
	border: 1px solid var(--pos-border-light);
	border-radius: 8px;
	overflow: hidden;
}

.batches-table {
	background: var(--pos-surface-raised);
}

.batches-table thead {
	background: var(--pos-surface-muted);
}

.batches-table thead th {
	font-weight: 700;
	color: var(--pos-text-secondary);
	border-bottom: 2px solid var(--pos-border-light);
	padding: 12px 16px;
}

.batches-table tbody tr {
	border-bottom: 1px solid var(--pos-border-light);
	transition: background-color 0.2s ease;
}

.batches-table tbody tr:hover {
	background-color: rgba(var(--v-theme-primary), 0.04);
}

.batches-table tbody td {
	padding: 12px 16px;
	vertical-align: middle;
}

.border-top {
	border-top: 1px solid var(--pos-border-light);
}

.info-item {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 8px 0;
}

.info-label {
	font-weight: 600;
	color: var(--pos-text-secondary);
	min-width: 120px;
}

.info-value {
	color: var(--pos-text-primary);
	word-break: break-word;
}

.opacity-50 {
	opacity: 0.5;
}
</style>
