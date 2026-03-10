<template>
  <div class="container">
    <a-typography-title :heading="5">
      📊 集团今日快报 ({{ currentDate }})
    </a-typography-title>
    
    <a-grid :cols="24" :col-gap="16" :row-gap="16">
      <a-grid-item :span="24">
        <a-space>
            <a-button type="primary" status="success" @click="fetchData" :loading="loading">
                <template #icon><icon-refresh /></template>
                刷新数据
            </a-button>
            <a-checkbox v-model="appStore.showUSD">显示美元 (USD)</a-checkbox>
        </a-space>
      </a-grid-item>

      <a-grid-item :span="24">
        <a-card :loading="loading">
            <template #title>各公司关键指标</template>
            <a-table :data="tableData" :pagination="false" :bordered="{cell:true}" stripe>
                <template #columns>
                    <a-table-column title="国家/地区" data-index="country">
                        <template #cell="{ record }">
                            <span style="font-size: 1.1em; margin-right: 6px;">{{ record.flag }}</span>
                            <b>{{ record.name }}</b>
                        </template>
                    </a-table-column>
                    <a-table-column title="今日销售" data-index="sales_today" align="right">
                        <template #cell="{ record }">
                            {{ formatCurrency(record.sales_today, record.currency, record.rate) }}
                        </template>
                    </a-table-column>
                    <a-table-column title="本月累计" data-index="sales_month" align="right">
                         <template #cell="{ record }">
                            {{ formatCurrency(record.sales_month, record.currency, record.rate) }}
                        </template>
                    </a-table-column>
                    <a-table-column title="今日产量" data-index="prod_today" align="right">
                        <template #cell="{ record }">
                            {{ record.prod_today ? record.prod_today.toLocaleString() : '-' }}
                        </template>
                    </a-table-column>
                    <a-table-column title="资金余额" data-index="balance" align="right">
                         <template #cell="{ record }">
                            {{ formatCurrency(record.balance, record.currency, record.rate) }}
                        </template>
                    </a-table-column>
                    <a-table-column title="状态" data-index="warnings" align="center">
                        <template #cell="{ record }">
                            <a-tag color="red" v-if="record.error">
                                {{ record.error }}
                            </a-tag>
                            <a-tag color="orange" v-else-if="record.warnings && record.warnings.length > 0">
                                {{ record.warnings.join(', ') }}
                            </a-tag>
                            <a-tag color="green" v-else>运行正常</a-tag>
                        </template>
                    </a-table-column>
                </template>
            </a-table>
        </a-card>
      </a-grid-item>
    </a-grid>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted } from 'vue';
import { IconRefresh } from '@arco-design/web-vue/es/icon';
import { useAppStore } from '../../stores/app';
import { fetchGroupDailySummary } from '../../api';

const appStore = useAppStore();
const currentDate = new Date().toISOString().split('T')[0];
const loading = ref(false);
const tableData = ref<any[]>([]);

const formatCurrency = (val: number, currency: string, rate: number) => {
    if (val === undefined || val === null) return '-';
    
    if (appStore.showUSD) {
        if (!rate || rate === 0) return '-';
        const usdVal = val / rate;
        return `$ ${usdVal.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}`;
    }
    return `${currency} ${val.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}`;
};

const fetchData = async () => {
    loading.value = true;
    try {
        const res = await fetchGroupDailySummary();
        tableData.value = res;
    } catch (err) {
        console.error(err);
        // Handle error (e.g., show notification)
    } finally {
        loading.value = false;
    }
};

onMounted(() => {
    fetchData();
});
</script>

<style scoped>
.container {
  padding: 20px;
}
</style>
