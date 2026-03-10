<template>
  <div class="sales-detail-table">
    <a-space direction="vertical" fill>
      <a-form :model="queryForm" layout="inline">
        <a-form-item field="dateRange" label="Date Range">
          <a-range-picker v-model="queryForm.dateRange" style="width: 260px" />
        </a-form-item>
        <a-form-item field="customerName" label="Customer">
          <a-input v-model="queryForm.customerName" placeholder="Search Customer" allow-clear />
        </a-form-item>
        <a-form-item field="productName" label="Product">
          <a-input v-model="queryForm.productName" placeholder="Search Product" allow-clear />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" @click="handleSearch" :loading="loading">
            <template #icon><icon-search /></template>
            Query
          </a-button>
        </a-form-item>
      </a-form>

      <a-table
        :columns="columns"
        :data="data"
        :loading="loading"
        :pagination="pagination"
        @page-change="handlePageChange"
        size="small"
      >
        <template #price="{ record }">
          {{ record.price?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
        </template>
        <template #amount="{ record }">
          {{ record.amount?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
        </template>
        <template #summary="{ record }">
          <a-tooltip :content="record.summary" v-if="record.summary && record.summary.length > 20">
            <span>{{ record.summary.substring(0, 20) }}...</span>
          </a-tooltip>
          <span v-else>{{ record.summary }}</span>
        </template>
      </a-table>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { IconSearch } from '@arco-design/web-vue/es/icon';
import { fetchSalesDetails } from '@/api';
import dayjs from 'dayjs';

const props = defineProps<{
  tenantKey: string;
}>();

const loading = ref(false);
const data = ref<any[]>([]);
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
});

const queryForm = reactive({
  dateRange: [dayjs().startOf('month').format('YYYY-MM-DD'), dayjs().format('YYYY-MM-DD')],
  customerName: '',
  productName: '',
});

const columns = [
  { title: 'Date', dataIndex: 'date', width: 120 },
  { title: 'Bill No', dataIndex: 'bill_no', width: 150 },
  { title: 'Customer', dataIndex: 'customer_name', ellipsis: true, tooltip: true },
  { title: 'Product', dataIndex: 'product_name', ellipsis: true, tooltip: true },
  { title: 'Spec', dataIndex: 'standard', width: 100, ellipsis: true },
  { title: 'Qty', dataIndex: 'qty', width: 80, align: 'right' as const },
  { title: 'Price', dataIndex: 'price', width: 100, align: 'right' as const, slotName: 'price' },
  { title: 'Amount', dataIndex: 'amount', width: 120, align: 'right' as const, slotName: 'amount' },
  { title: 'Summary', dataIndex: 'summary', slotName: 'summary', ellipsis: true },
];

const fetchData = async () => {
  loading.value = true;
  try {
    const params = {
      start_date: queryForm.dateRange?.[0] || '',
      end_date: queryForm.dateRange?.[1] || '',
      customer_name: queryForm.customerName || undefined,
      product_name: queryForm.productName || undefined,
      page: pagination.current,
      page_size: pagination.pageSize,
    };
    
    const res = await fetchSalesDetails(props.tenantKey, params);
    data.value = res.items;
    pagination.total = res.total;
  } catch (err) {
    // Error handled by interceptor
  } finally {
    loading.value = false;
  }
};

const handleSearch = () => {
  pagination.current = 1;
  fetchData();
};

const handlePageChange = (page: number) => {
  pagination.current = page;
  fetchData();
};

onMounted(() => {
  fetchData();
});
</script>

<style scoped>
.sales-detail-table {
  padding: 16px 0;
}
</style>
