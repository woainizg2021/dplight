<template>
  <div class="dashboard-container">
    <!-- 顶部信息栏 -->
    <div class="header-bar">
      <div class="date-info">
        <span class="current-date">{{ currentDate }}</span>
        <span class="update-time">数据更新时间: {{ updateTime }}</span>
      </div>
      <div class="header-actions">
        <a-space>
          <a-switch 
            v-model="companyStore.showUSD"
            checked-text="USD" 
            unchecked-text="本币"
            type="round"
          />
          <a-button type="primary" @click="refreshData">
            <template #icon><icon-refresh /></template>
            刷新
          </a-button>
        </a-space>
      </div>
    </div>

    <!-- 公司数据卡片 -->
    <div class="company-cards">
      <div 
        v-for="company in companies" 
        :key="company.key"
        class="company-card"
        :class="{ 'has-alerts': company.alerts.length > 0 }"
      >
        <div class="card-header">
          <h3 class="company-name">{{ company.short_name }}</h3>
          <div v-if="company.alerts.length > 0" class="alert-badge">
            <a-tooltip :content="formatAlerts(company.alerts)">
              <icon-exclamation-circle class="alert-icon" />
            </a-tooltip>
          </div>
        </div>
        
        <div class="card-content">
          <div class="metric-item">
            <div class="metric-label">今日销售</div>
            <div class="metric-value">{{ formatCurrency(company.today_sales, company.currency, companyStore.showUSD) }}</div>
            <div class="metric-progress">
              <a-progress 
                :percent="getSalesProgress(company)"
                :status="getSalesProgressStatus(company)"
                size="small"
              />
            </div>
          </div>
          
          <div class="metric-item">
            <div class="metric-label">本月销售</div>
            <div class="metric-value">{{ formatCurrency(company.mtd_sales, company.currency, companyStore.showUSD) }}</div>
          </div>
          
          <div class="metric-item">
            <div class="metric-label">今日产量</div>
            <div class="metric-value">{{ formatProduction(company.today_production) }}</div>
          </div>
          
          <div class="metric-item">
            <div class="metric-label">银行余额</div>
            <div class="metric-value">{{ formatCurrency(company.bank_balance, company.currency, companyStore.showUSD) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 销售趋势图表 -->
    <div class="sales-trend-section">
      <div class="chart-header">
        <h3>近7天销售趋势</h3>
        <div class="chart-actions">
          <a-radio-group v-model="chartType" size="small">
            <a-radio value="line">折线图</a-radio>
            <a-radio value="bar">柱状图</a-radio>
          </a-radio-group>
        </div>
      </div>
      
      <div class="chart-container">
        <div ref="chartRef" class="chart"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Message } from '@arco-design/web-vue'
import { IconRefresh, IconExclamationCircle } from '@arco-design/web-vue/es/icon'
import * as echarts from 'echarts'
import { useCompanyStore } from '@/stores/company'
import { formatCurrency } from '@/utils/formatter'
import { dashboardAPI } from '@/api'

const { t } = useI18n()
const companyStore = useCompanyStore()

// 数据状态
const loading = ref(false)
const dashboardData = ref<any>(null)
const chartType = ref<'line' | 'bar'>('line')
const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null

// 计算属性
const currentDate = computed(() => {
  return new Date().toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long'
  })
})

const updateTime = computed(() => {
  return dashboardData.value?.updated_at || new Date().toLocaleString('zh-CN')
})

const companies = computed(() => {
  return dashboardData.value?.companies || []
})

const salesTrend = computed(() => {
  return dashboardData.value?.sales_trend || { dates: [], UGANDA: [], NIGERIA: [], KENYA: [], KENYA_AUDIO: [], DRC: [] }
})

// 方法
const loadDashboardData = async () => {
  loading.value = true
  try {
    const response = await dashboardAPI.getTodayDashboard()
    dashboardData.value = response
    updateChart()
  } catch (error) {
    Message.error('获取仪表板数据失败')
    console.error('Failed to load dashboard data:', error)
  } finally {
    loading.value = false
  }
}

const refreshData = async () => {
  await loadDashboardData()
  Message.success('数据已刷新')
}

const formatAlerts = (alerts: any[]) => {
  return alerts.map(alert => alert.msg).join('\n')
}

const getSalesProgress = (company: any) => {
  if (company.mtd_target <= 0) return 0
  return Math.min((company.mtd_sales / company.mtd_target) * 100, 100)
}

const getSalesProgressStatus = (company: any) => {
  const progress = getSalesProgress(company)
  if (progress >= 100) return 'success'
  if (progress >= 80) return 'warning'
  return 'danger'
}

const formatProduction = (production: number) => {
  if (production >= 10000) {
    return `${(production / 10000).toFixed(1)}万pcs`
  }
  return `${production.toFixed(0)}pcs`
}

const updateChart = () => {
  if (!chartInstance || !salesTrend.value.dates.length) return

  const option = {
    title: {
      text: '销售趋势',
      left: 'center',
      textStyle: {
        fontSize: 14,
        fontWeight: 'normal'
      }
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        let html = `<div style="font-weight: bold; margin-bottom: 5px;">${params[0].axisValue}</div>`
        params.forEach((param: any) => {
          const company = companies.value.find((c: any) => c.key === param.seriesName)
          const currency = company?.currency || 'USD'
          html += `<div style="display: flex; align-items: center; margin: 2px 0;">
            <span style="display: inline-block; width: 10px; height: 10px; background-color: ${param.color}; border-radius: 50%; margin-right: 5px;"></span>
            <span style="flex: 1;">${company?.short_name || param.seriesName}:</span>
            <span style="font-weight: bold;">${formatCurrency(param.value, currency, companyStore.showUSD)}</span>
          </div>`
        })
        return html
      }
    },
    legend: {
      data: ['乌干达', '尼日利亚', '肯尼亚', '肯尼亚音箱', '刚果金'],
      bottom: 0
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: chartType.value === 'bar',
      data: salesTrend.value.dates.map((date: string) => {
        const d = new Date(date)
        return `${d.getMonth() + 1}/${d.getDate()}`
      }),
      axisLabel: {
        rotate: 45
      }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (value: number) => {
          if (value >= 1000000) {
            return `${(value / 1000000).toFixed(1)}M`
          } else if (value >= 1000) {
            return `${(value / 1000).toFixed(0)}K`
          }
          return value.toString()
        }
      }
    },
    series: [
      {
        name: '乌干达',
        type: chartType.value,
        data: salesTrend.value.UGANDA,
        smooth: true,
        lineStyle: { width: 2 },
        itemStyle: { color: '#1890ff' }
      },
      {
        name: '尼日利亚',
        type: chartType.value,
        data: salesTrend.value.NIGERIA,
        smooth: true,
        lineStyle: { width: 2 },
        itemStyle: { color: '#52c41a' }
      },
      {
        name: '肯尼亚',
        type: chartType.value,
        data: salesTrend.value.KENYA,
        smooth: true,
        lineStyle: { width: 2 },
        itemStyle: { color: '#faad14' }
      },
      {
        name: '肯尼亚音箱',
        type: chartType.value,
        data: salesTrend.value.KENYA_AUDIO,
        smooth: true,
        lineStyle: { width: 2 },
        itemStyle: { color: '#f5222d' }
      },
      {
        name: '刚果金',
        type: chartType.value,
        data: salesTrend.value.DRC,
        smooth: true,
        lineStyle: { width: 2 },
        itemStyle: { color: '#722ed1' }
      }
    ]
  }

  chartInstance.setOption(option, true)
}

// 生命周期
onMounted(async () => {
  if (chartRef.value) {
    chartInstance = echarts.init(chartRef.value)
    
    // 响应式
    const resizeObserver = new ResizeObserver(() => {
      chartInstance?.resize()
    })
    resizeObserver.observe(chartRef.value)
  }
  
  await loadDashboardData()
})

// 监听图表类型变化
watch(chartType, () => {
  updateChart()
})

// 监听公司切换
watch(() => companyStore.currentCompany, () => {
  loadDashboardData()
})

// 监听 USD 切换
watch(() => companyStore.showUSD, () => {
  // 强制刷新组件或重新渲染
  // 这里 formatCurrency 是在模板中调用的，只要 showUSD 变化，Vue 会自动重新渲染模板
  // 但图表是 echarts 实例，需要手动更新
  updateChart()
})
</script>

<style scoped lang="less">
.dashboard-container {
  padding: 20px;
  background: #f5f5f5;
  min-height: 100vh;
}

.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  padding: 16px 24px;
  border-radius: 8px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.date-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.current-date {
  font-size: 18px;
  font-weight: 600;
  color: #262626;
}

.update-time {
  font-size: 12px;
  color: #8c8c8c;
}

.company-cards {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.company-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
  
  &:hover {
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
    transform: translateY(-2px);
  }
  
  &.has-alerts {
    border-left: 4px solid #ff4d4f;
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.company-name {
  font-size: 16px;
  font-weight: 600;
  color: #262626;
  margin: 0;
}

.alert-badge {
  .alert-icon {
    color: #ff4d4f;
    font-size: 16px;
    cursor: pointer;
  }
}

.card-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metric-label {
  font-size: 12px;
  color: #8c8c8c;
}

.metric-value {
  font-size: 16px;
  font-weight: 600;
  color: #262626;
}

.metric-progress {
  margin-top: 4px;
}

.sales-trend-section {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  
  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #262626;
  }
}

.chart-container {
  width: 100%;
  height: 300px;
}

.chart {
  width: 100%;
  height: 100%;
}

// 响应式设计
@media (max-width: 1200px) {
  .company-cards {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 768px) {
  .company-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .header-bar {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }
}

@media (max-width: 480px) {
  .company-cards {
    grid-template-columns: 1fr;
  }
  
  .chart-header {
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
  }
}
</style>