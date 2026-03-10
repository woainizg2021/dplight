<template>
  <a-layout class="layout-demo">
    <a-layout-header>
      <div class="header-content">
        <div class="left-side">
          <div class="logo">
             🌍 Dplight ERP <a-tag color="arcoblue" style="margin-left: 8px;">V9.0</a-tag>
          </div>
          <a-button type="text" @click="toggleCollapse">
            <icon-menu-fold v-if="!collapsed" />
            <icon-menu-unfold v-else />
          </a-button>
        </div>
        <div class="right-side">
           <a-space>
             <a-switch 
               v-model="companyStore.showUSD" 
               checked-text="USD" 
               unchecked-text="本币"
               type="round"
             />
             
             <a-select 
               :style="{width:'160px'}" 
               v-model="companyStore.currentCompany" 
               @change="handleCompanyChange"
             >
                <a-option 
                  v-for="company in availableCompanies" 
                  :key="company.key" 
                  :value="company.key"
                >
                  {{ company.label }}
                </a-option>
             </a-select>
             
             <a-dropdown @select="handleUserMenuClick">
               <a-avatar :size="32" style="cursor: pointer; background-color: #3370ff;">
                 {{ authStore.user?.charAt(0).toUpperCase() || 'U' }}
               </a-avatar>
               <template #content>
                 <a-doption value="logout">
                   <template #icon><icon-export /></template>
                   退出登录
                 </a-doption>
               </template>
             </a-dropdown>
           </a-space>
        </div>
      </div>
    </a-layout-header>
    <a-layout>
      <a-layout-sider
        hide-trigger
        collapsible
        :collapsed="collapsed"
        :width="220"
      >
        <a-menu
          :default-open-keys="['Dashboard', 'Sales', 'Production', 'Stock', 'Finance', 'General', 'Settings']"
          :selected-keys="selectedKeys"
          @menu-item-click="onClickMenuItem"
        >
          <!-- 📊 驾驶舱 -->
          <a-sub-menu key="Dashboard" v-if="canAccessDashboard">
            <template #icon><icon-dashboard /></template>
            <template #title>驾驶舱</template>
            <a-menu-item key="GroupOverview">今日快报</a-menu-item>
            <a-menu-item key="GroupMonthly">月度对比</a-menu-item>
            <a-menu-item key="SalesPerformance">五司销售绩效看板</a-menu-item>
            <a-menu-item key="FinanceOverviewDashboard">财务概览</a-menu-item>
            <a-menu-item key="ProductionReport">生产报告</a-menu-item>
            <a-menu-item key="SalesReport">销售报告</a-menu-item>
          </a-sub-menu>
          
          <!-- 🛒 销售类 -->
          <a-sub-menu key="Sales">
            <template #icon><icon-bar-chart /></template>
            <template #title>销售类</template>
            <a-menu-item key="SalesQuery">销售查询</a-menu-item>
            <a-menu-item key="SalesTarget">销售目标进度</a-menu-item>
            <a-menu-item key="CustomerRank">客户销售排行榜</a-menu-item>
            <a-menu-item key="StaffRank">业务员销售排行榜</a-menu-item>
            <a-menu-item key="CategoryRank">大类销售排行榜</a-menu-item>
            <a-menu-item key="SkuRank">存货销售排行榜</a-menu-item>
            <a-menu-item key="Stockout">热销款断货天数</a-menu-item>
            <a-menu-item key="AvailableDays">可销天数查询</a-menu-item>
          </a-sub-menu>

          <!-- 🏭 生产类 -->
          <a-sub-menu key="Production">
            <template #icon><icon-tool /></template>
            <template #title>生产类</template>
            <a-menu-item key="ProductionProgress">生产进度表</a-menu-item>
            <a-menu-item key="ProductionTarget">生产目标进度</a-menu-item>
            <a-menu-item key="MaterialRequest">生产领料单</a-menu-item>
            <a-menu-item key="Completion">生成完工验收单</a-menu-item>
            <a-menu-item key="Efficiency">工厂人效对比</a-menu-item>
            <a-menu-item key="Capacity">产能分析系统</a-menu-item>
            <a-menu-item key="BomQuery">BOM结构查询</a-menu-item>
            <a-menu-item key="Procurement">原材料采购查询</a-menu-item>
          </a-sub-menu>

          <!-- 🏬 仓库类 -->
          <a-sub-menu key="Stock">
            <template #icon><icon-storage /></template>
            <template #title>仓库类</template>
            <a-menu-item key="StockReport">库存报告</a-menu-item>
            <a-menu-item key="RawMaterial">原材料库存查询</a-menu-item>
            <a-menu-item key="FinishedGoods">成品库存查询</a-menu-item>
            <a-menu-item key="InoutDetail">出入库明细查询</a-menu-item>
          </a-sub-menu>

          <!-- 💰 财务类 -->
          <a-sub-menu key="Finance" v-if="canAccessFinance">
            <template #icon><icon-file /></template>
            <template #title>财务类</template>
            <a-menu-item key="AR">应收账款</a-menu-item>
            <a-menu-item key="ARQuery">应收款查询</a-menu-item>
            <a-menu-item key="Expense">费用查询</a-menu-item>
            <a-menu-item key="Cash">资金查询</a-menu-item>
            <a-menu-item key="Voucher">凭证列表</a-menu-item>
          </a-sub-menu>

          <!-- 📋 综合类 -->
          <a-sub-menu key="General">
            <template #icon><icon-apps /></template>
            <template #title>综合类</template>
            <a-menu-item key="HRReport">人员报告</a-menu-item>
            <a-menu-item key="PXCAnalysis">产销存分析</a-menu-item>
            <a-menu-item key="NewProduct">新品调研</a-menu-item>
            <a-menu-item key="VoucherCheck">单据核对系统</a-menu-item>
            <a-menu-item key="History">经营历程</a-menu-item>
            <a-menu-item key="Tasks">任务中心</a-menu-item>
            <a-menu-item key="Logs">系统日志</a-menu-item>
            <a-menu-item key="Cloud">360云盘</a-menu-item>
          </a-sub-menu>
          
          <!-- ⚙️ 系统设置 -->
          <a-sub-menu key="Settings" v-if="authStore.isSuperuser">
            <template #icon><icon-settings /></template>
            <template #title>系统设置</template>
            <a-menu-item key="Budget">预算录入</a-menu-item>
            <a-menu-item key="ExchangeRate">汇率维护</a-menu-item>
            <a-menu-item key="Users">用户管理</a-menu-item>
          </a-sub-menu>
        </a-menu>
      </a-layout-sider>
      <a-layout-content class="content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script lang="ts" setup>
import { ref, computed, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useCompanyStore } from '@/stores/company';
import {
  IconMenuFold,
  IconMenuUnfold,
  IconDashboard,
  IconBarChart,
  IconStorage,
  IconFile,
  IconApps,
  IconTool,
  IconSettings,
  IconExport
} from '@arco-design/web-vue/es/icon';

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const companyStore = useCompanyStore();
const collapsed = ref(false);

const toggleCollapse = () => {
  collapsed.value = !collapsed.value;
};

// 当前选中的菜单项
const selectedKeys = computed(() => [route.name as string]);

// 权限判断
const canAccessDashboard = computed(() => {
  return authStore.isSuperuser || (authStore.roles && authStore.roles.includes('shareholder'));
});

const canAccessFinance = computed(() => {
  return authStore.isSuperuser || 
         (authStore.roles && (authStore.roles.includes('shareholder') || authStore.roles.includes('manager')));
});

// 可选公司列表
const availableCompanies = computed(() => {
  const companies = [
    { key: 'UGANDA', label: '🇺🇬 乌干达' },
    { key: 'NIGERIA', label: '🇳🇬 尼日利亚' },
    { key: 'KENYA', label: '🇰🇪 肯尼亚' },
    { key: 'KENYA_AUDIO', label: '🔊 肯尼亚音箱' },
    { key: 'DRC', label: '🇨🇩 刚果金' }
  ];
  
  // 过滤当前用户有权限的公司
  if (authStore.isSuperuser) {
    return companies;
  }
  
  return companies.filter(c => authStore.allowedCompanies.includes(c.key));
});

const handleCompanyChange = (val: any) => {
  companyStore.setCompany(val);
  // 刷新当前页面数据
  // 如果当前在仪表板页面，watch(companyStore.currentCompany) 会自动触发刷新
  // 但如果是其他页面，可能需要手动刷新或路由跳转
  // router.go(0) // 暴力刷新
};

const handleUserMenuClick = (val: any) => {
  if (val === 'logout') {
    authStore.logout();
    router.push('/login');
  }
};

const onClickMenuItem = (key: string) => {
  router.push({ name: key });
};
</script>

<style scoped>
.layout-demo {
  height: 100vh;
}
.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
  padding: 0 20px;
  background: var(--color-bg-2);
  border-bottom: 1px solid var(--color-border);
}
.left-side {
    display: flex;
    align-items: center;
    gap: 16px;
}
.logo {
    font-size: 18px;
    font-weight: bold;
    color: var(--color-text-1);
    display: flex;
    align-items: center;
}
.content {
  padding: 24px;
  background: var(--color-fill-2);
  overflow-y: auto;
}
</style>
