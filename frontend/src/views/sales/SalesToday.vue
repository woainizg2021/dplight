<template>
  <div class="container">
    <a-typography-title :heading="5">
      📊 今日销售详情 ({{ currentDate }}) - {{ tenantKey }}
    </a-typography-title>
    
    <a-grid :cols="24" :col-gap="16" :row-gap="16">
      <a-grid-item :span="24">
        <a-space>
            <a-date-picker v-model="currentDate" @change="fetchData" />
            <a-select v-model="tenantKey" @change="fetchData" style="width: 200px">
                <a-option value="UGANDA">🇺🇬 乌干达</a-option>
                <a-option value="NIGERIA">🇳🇬 尼日利亚</a-option>
                <a-option value="KENYA">🇰🇪 肯尼亚</a-option>
                <a-option value="KENYA_AUDIO">🔊 肯尼亚音响</a-option>
                <a-option value="DRC">🇨🇩 刚果金</a-option>
            </a-select>
            <a-button type="primary" status="success" @click="fetchData" :loading="loading">
                <template #icon><icon-refresh /></template>
                查询
            </a-button>
        </a-space>
      </a-grid-item>

      <a-grid-item :span="16">
        <a-card :loading="loading" title="销售流水">
            <a-table :data="transactions" :pagination="false" :bordered="{cell:true}" stripe :scroll="{ y: 500 }">
                <template #columns>
                    <a-table-column title="单号" data-index="display_number" width="100"></a-table-column>
                    <a-table-column title="手工单号" data-index="manual_number" width="120"></a-table-column>
                    <a-table-column title="客户" data-index="customer_name"></a-table-column>
                    <a-table-column title="销售金额" data-index="amount" align="right">
                        <template #cell="{ record }">
                            {{ record.amount?.toLocaleString() }}
                        </template>
                    </a-table-column>
                    <a-table-column title="现金" data-index="cash" align="right">
                        <template #cell="{ record }">
                            {{ record.cash?.toLocaleString() }}
                        </template>
                    </a-table-column>
                    <a-table-column title="银行" data-index="bank" align="right">
                        <template #cell="{ record }">
                            {{ record.bank?.toLocaleString() }}
                        </template>
                    </a-table-column>
                    <a-table-column title="应收账款" data-index="receivable" align="right">
                        <template #cell="{ record }">
                            <span :style="{ color: record.receivable > 0 ? 'red' : 'inherit' }">
                                {{ record.receivable?.toLocaleString() }}
                            </span>
                        </template>
                    </a-table-column>
                </template>
            </a-table>
            
            <div style="margin-top: 16px; font-weight: bold; text-align: right;">
                合计销售: {{ totalSales.toLocaleString() }} | 
                现金: {{ totalCash.toLocaleString() }} | 
                银行: {{ totalBank.toLocaleString() }} | 
                应收: {{ totalAR.toLocaleString() }}
            </div>
        </a-card>
      </a-grid-item>
      
      <a-grid-item :span="8">
        <a-card :loading="loading" title="费用支出 (现金/银行流出)">
            <a-table :data="expenses" :pagination="false" :bordered="{cell:true}">
                <template #columns>
                    <a-table-column title="账户" data-index="name"></a-table-column>
                    <a-table-column title="费用" data-index="fee" align="right">
                        <template #cell="{ record }">
                            {{ record.fee?.toLocaleString() }}
                        </template>
                    </a-table-column>
                    <a-table-column title="总支出" data-index="total" align="right">
                        <template #cell="{ record }">
                            <b>{{ record.total?.toLocaleString() }}</b>
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
import { ref, onMounted, computed } from 'vue';
import { IconRefresh } from '@arco-design/web-vue/es/icon';
import { fetchSalesDailyDetails } from '../../api';

const currentDate = ref(new Date().toISOString().split('T')[0]);
const tenantKey = ref('UGANDA');
const loading = ref(false);
const transactions = ref<any[]>([]);
const expenses = ref<any[]>([]);

const totalSales = computed(() => transactions.value.reduce((sum, t) => sum + (t.amount || 0), 0));
const totalCash = computed(() => transactions.value.reduce((sum, t) => sum + (t.cash || 0), 0));
const totalBank = computed(() => transactions.value.reduce((sum, t) => sum + (t.bank || 0), 0));
const totalAR = computed(() => transactions.value.reduce((sum, t) => sum + (t.receivable || 0), 0));

const fetchData = async () => {
    loading.value = true;
    try {
        const res = await fetchSalesDailyDetails(tenantKey.value, currentDate.value || '');
        if (res) {
          transactions.value = res.transactions;
          expenses.value = res.expenses;
        }
    } catch (err) {
        console.error(err);
        transactions.value = [];
        expenses.value = [];
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
