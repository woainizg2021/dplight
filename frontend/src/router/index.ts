import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import DefaultLayout from '@/components/layout/DefaultLayout.vue'
import Login from '@/views/auth/Login.vue' // Assuming Login view exists or will be created

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/auth/Login.vue'),
      meta: { public: true }
    },
    {
      path: '/',
      component: DefaultLayout,
      redirect: '/dashboard/today',
      children: [
        // 📊 驾驶舱 (Dashboard)
        {
          path: 'dashboard',
          name: 'Dashboard',
          meta: { title: '驾驶舱', roles: ['shareholder'], superuserOnly: false },
          children: [
            {
              path: 'today',
              name: 'GroupOverview',
              component: () => import('@/views/dashboard/GroupOverview.vue'),
              meta: { title: '今日快报' }
            },
            {
              path: 'monthly',
              name: 'GroupMonthly',
              component: () => import('@/views/dashboard/GroupMonthly.vue'),
              meta: { title: '月度对比' }
            },
            {
              path: 'sales-performance',
              name: 'SalesPerformance',
              component: () => import('@/views/dashboard/SalesPerformance.vue'),
              meta: { title: '五司销售绩效看板' }
            },
            // Placeholders for other dashboard items
            {
              path: 'finance-overview',
              name: 'FinanceOverviewDashboard',
              component: () => import('@/views/common/Placeholder.vue'),
              meta: { title: '财务概览' }
            },
            {
              path: 'production-report',
              name: 'ProductionReport',
              component: () => import('@/views/common/Placeholder.vue'),
              meta: { title: '生产报告' }
            },
            {
              path: 'sales-report',
              name: 'SalesReport',
              component: () => import('@/views/common/Placeholder.vue'),
              meta: { title: '销售报告' }
            }
          ]
        },
        // 🛒 销售类 (Sales)
        {
          path: 'sales',
          name: 'Sales',
          meta: { title: '销售类' },
          children: [
            {
              path: 'query',
              name: 'SalesQuery',
              component: () => import('@/views/sales/SalesQuery.vue'),
              meta: { title: '销售查询' }
            },
            // Add other sales routes as placeholders
            { path: 'target', name: 'SalesTarget', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '销售目标进度' } },
            { path: 'customer-rank', name: 'CustomerRank', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '客户销售排行榜' } },
            { path: 'staff-rank', name: 'StaffRank', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '业务员销售排行榜' } },
            { path: 'category-rank', name: 'CategoryRank', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '大类销售排行榜' } },
            { path: 'sku-rank', name: 'SkuRank', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '存货销售排行榜' } },
            { path: 'stockout', name: 'Stockout', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '热销款断货天数' } },
            { path: 'available-days', name: 'AvailableDays', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '可销天数查询' } },
          ]
        },
        // 🏭 生产类 (Production)
        {
          path: 'production',
          name: 'Production',
          meta: { title: '生产类' },
          children: [
            { path: 'progress', name: 'ProductionProgress', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '生产进度表' } },
            { path: 'target', name: 'ProductionTarget', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '生产目标进度' } },
            { path: 'material-request', name: 'MaterialRequest', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '生产领料单' } },
            { path: 'completion', name: 'Completion', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '生成完工验收单' } },
            { path: 'efficiency', name: 'Efficiency', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '工厂人效对比' } },
            { path: 'capacity', name: 'Capacity', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '产能分析系统' } },
            { path: 'bom', name: 'BomQuery', component: () => import('@/views/common/Placeholder.vue'), meta: { title: 'BOM结构查询' } },
            { path: 'procurement', name: 'Procurement', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '原材料采购查询' } },
          ]
        },
        // 🏬 仓库类 (Stock)
        {
          path: 'stock',
          name: 'Stock',
          meta: { title: '仓库类' },
          children: [
            { path: 'report', name: 'StockReport', component: () => import('@/views/stock/StockQuery.vue'), meta: { title: '库存报告' } }, // Reusing StockQuery for now
            { path: 'raw-material', name: 'RawMaterial', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '原材料库存查询' } },
            { path: 'finished-goods', name: 'FinishedGoods', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '成品库存查询' } },
            { path: 'inout-detail', name: 'InoutDetail', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '出入库明细查询' } },
          ]
        },
        // 💰 财务类 (Finance) - 需 role=manager 以上
        {
          path: 'finance',
          name: 'Finance',
          meta: { title: '财务类', roles: ['manager', 'shareholder'] },
          children: [
            { path: 'ar', name: 'AR', component: () => import('@/views/finance/FinanceOverview.vue'), meta: { title: '应收账款' } },
            { path: 'ar-query', name: 'ARQuery', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '应收款查询' } },
            { path: 'expense', name: 'Expense', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '费用查询' } },
            { path: 'cash', name: 'Cash', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '资金查询' } },
            { path: 'voucher', name: 'Voucher', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '凭证列表' } },
          ]
        },
        // 📋 综合类 (General)
        {
          path: 'general',
          name: 'General',
          meta: { title: '综合类' },
          children: [
            { path: 'hr-report', name: 'HRReport', component: () => import('@/views/general/HR.vue'), meta: { title: '人员报告' } },
            { path: 'pxc-analysis', name: 'PXCAnalysis', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '产销存分析' } },
            { path: 'new-product', name: 'NewProduct', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '新品调研' } },
            { path: 'voucher-check', name: 'VoucherCheck', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '单据核对系统' } },
            { path: 'history', name: 'History', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '经营历程' } },
            { path: 'tasks', name: 'Tasks', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '任务中心' } },
            { path: 'logs', name: 'Logs', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '系统日志' } },
            { path: 'cloud', name: 'Cloud', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '360云盘' } },
          ]
        },
        // ⚙️ 系统设置 (Settings) - 仅 superuser
        {
          path: 'settings',
          name: 'Settings',
          meta: { title: '系统设置', superuserOnly: true },
          children: [
            { path: 'budget', name: 'Budget', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '预算录入' } },
            { path: 'exchange-rate', name: 'ExchangeRate', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '汇率维护' } },
            { path: 'users', name: 'Users', component: () => import('@/views/common/Placeholder.vue'), meta: { title: '用户管理' } },
          ]
        }
      ]
    },
    // 403 Forbidden
    {
        path: '/403',
        name: 'Forbidden',
        component: () => import('@/views/common/Placeholder.vue'), // Should be a 403 page
        meta: { title: '403 Forbidden', public: true }
    }
  ]
})

// Route Guard
router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()
  
  if (to.meta.public) {
    next()
    return
  }
  
  // Check auth
  if (!authStore.token) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }
  
  // Check superuser
  if (to.meta.superuserOnly && !authStore.isSuperuser) {
    next({ name: 'Forbidden' })
    return
  }
  
  // Check roles
  if (to.meta.roles) {
    const requiredRoles = to.meta.roles as string[]
    // If user is superuser, bypass role check (as per requirement: boss888 -> all)
    if (authStore.isSuperuser) {
        next()
        return
    }
    
    // Check if user has any of the required roles
    // authStore.roles is an array of roles the user has
    // Wait, authStore.roles might be a single string or array. The mock data says "role": "shareholder". 
    // Let's assume authStore.role is a string or array.
    // In auth.ts it is roles: string[].
    const userRoles = authStore.roles
    const hasRole = requiredRoles.some(role => userRoles.includes(role))
    
    if (!hasRole) {
      next({ name: 'Forbidden' })
      return
    }
  }
  
  next()
})

export default router
