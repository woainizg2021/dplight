<template>
  <div class="sku-ranking-table">
    <a-space direction="vertical" fill>
      <a-form :model="queryForm" layout="inline">
        <a-form-item field="dateRange" label="Date Range">
          <a-range-picker v-model="queryForm.dateRange" style="width: 260px" />
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
        :pagination="false"
        size="small"
      >
        <template #index="{ rowIndex }">
          {{ rowIndex + 1 }}
        </template>
        <template #value="{ record }">
          {{ record.value?.toLocaleString() }}
        </template>
        <template #amount="{ record }">
          {{ record.amount?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
        </template>
      </a-table>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { IconSearch } from '@arco-design/web-vue/es/icon';
import { fetchSkuRanking } from '@/api';
import dayjs from 'dayjs';

const props = defineProps<{
  tenantKey: string;
}>();

const loading = ref(false);
const data = ref<any[]>([]);

const queryForm = reactive({
  dateRange: [dayjs().startOf('month').format('YYYY-MM-DD'), dayjs().format('YYYY-MM-DD')],
});

const columns = [
  { title: '#', slotName: 'index', width: 60, align: 'center' as const },
  { title: 'Product Name', dataIndex: 'name' },
  { title: 'Sales Qty', dataIndex: 'value', slotName: 'value', align: 'right' as const },
  { title: 'Total Amount', dataIndex: 'amount', slotName: 'amount', align: 'right' as const },
];

const fetchData = async () => {
  loading.value = true;
  try {
    const res = await fetchSkuRanking(
      props.tenantKey, 
      queryForm.dateRange?.[0] || '', 
      queryForm.dateRange?.[1] || ''
    );
    data.value = res;
  } catch (err) {
    // Error handled by interceptor
  } finally {
    loading.value = false;
  }
};

const handleSearch = () => {
  fetchData();
};

onMounted(() => {
  fetchData();
});
</script>

<style scoped>
.sku-ranking-table {
  padding: 16px 0;
}
</style>
