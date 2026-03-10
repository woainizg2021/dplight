<template>
  <div class="group-monthly">
    <a-page-header title="集团月度对比 (Group Monthly Comparison)" />
    
    <!-- 月份选择器 -->
    <div class="month-selector">
      <a-space>
        <span>选择月份：</span>
        <a-date-picker 
          v-model="selectedMonth" 
          type="month"
          format="YYYY年MM月"
          @change="handleMonthChange"
        />
        <a-switch 
          v-model="companyStore.showUSD"
          checked-text="USD" 
          unchecked-text="本币"
          type="round"
        />
        <a-button type="primary" @click="loadData">
          <template #icon><icon-refresh /></template>
          刷新
        </a-button>
      </a-space>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <a-spin tip="加载中..." />
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error-container">
      <a-alert :title="error" type="error" />
    </div>

    <!-- 图表容器 -->
    <div v-else class="charts-container">
      <!-- 收入对比 -->
      <div class="chart-section">
        <h3>收入对比 (Revenue Comparison)</h3>
        <div ref="revenueChart" class="chart"></div>
      </div>

      <!-- 毛利率对比 -->
      <div class="chart-section">
        <h3>毛利率对比 (Gross Margin Comparison)</h3>
        <div ref="grossMarginChart" class="chart"></div>
      </div>

      <!-- 净利率对比 -->
      <div class="chart-section">
        <h3>净利率对比 (Net Margin Comparison)</h3>
        <div ref="netMarginChart" class="chart"></div>
      </div>

      <!-- 人均产值对比 -->
      <div class="chart-section">
        <h3>人均产值对比 (Revenue per Person Comparison)</h3>
        <div ref="revenuePerPersonChart" class="chart"></div>
      </div>

      <!-- DSO对比 -->
      <div class="chart-section">
        <h3>应收账款周转天数对比 (DSO Comparison)</h3>
        <div ref="dsoChart" class="chart"></div>
      </div>

      <!-- DIO对比 -->
      <div class="chart-section">
        <h3>库存周转天数对比 (DIO Comparison)</h3>
        <div ref="dioChart" class="chart"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { getCurrentInstance, onUnmounted } from 'vue'
import { useCompanyStore } from '@/stores/company'
import { formatCurrency } from '@/utils/formatter'

const { proxy } = getCurrentInstance() as any
const companyStore = useCompanyStore()

// 状态
const loading = ref(false)
const error = ref('')
const selectedMonth = ref(new Date())
const monthlyData = ref<any[]>([])

// 图表实例
const revenueChart = ref<HTMLElement>()
const grossMarginChart = ref<HTMLElement>()
const netMarginChart = ref<HTMLElement>()
const revenuePerPersonChart = ref<HTMLElement>()
const dsoChart = ref<HTMLElement>()
const dioChart = ref<HTMLElement>()

let revenueChartInstance: echarts.ECharts | null = null
let grossMarginChartInstance: echarts.ECharts | null = null
let netMarginChartInstance: echarts.ECharts | null = null
let revenuePerPersonChartInstance: echarts.ECharts | null = null
let dsoChartInstance: echarts.ECharts | null = null
let dioChartInstance: echarts.ECharts | null = null

// 公司名称映射
const companyNames = {
  UGANDA: '乌干达',
  NIGERIA: '尼日利亚', 
  KENYA: '肯尼亚',
  KENYA_AUDIO: '肯尼亚音箱',
  DRC: '刚果金'
}

// 加载月度对比数据
const loadData = async () => {
  loading.value = true
  error.value = ''
  
  try {
    const year = selectedMonth.value.getFullYear()
    const month = selectedMonth.value.getMonth() + 1
    
    const response = await proxy?.$api.get('/dashboard/monthly-compare', {
      params: { year, month }
    })
    
    if (response.data) {
      monthlyData.value = response.data.data
      await nextTick()
      renderCharts()
    }
  } catch (err: any) {
    error.value = err.message || '加载数据失败'
  } finally {
    loading.value = false
  }
}

// 月份变更处理
const handleMonthChange = () => {
  loadData()
}

// 渲染图表
const renderCharts = () => {
  if (!monthlyData.value.length) return

  // 分离灯具厂和音箱厂数据
  const lightingCompanies = monthlyData.value.filter(item => 
    item.company_key !== 'KENYA_AUDIO'
  )
  const audioCompanies = monthlyData.value.filter(item => 
    item.company_key === 'KENYA_AUDIO'
  )

  // 渲染收入对比图
  renderRevenueChart(lightingCompanies, audioCompanies)
  
  // 渲染毛利率对比图
  renderGrossMarginChart(lightingCompanies, audioCompanies)
  
  // 渲染净利率对比图
  renderNetMarginChart(lightingCompanies, audioCompanies)
  
  // 渲染人均产值对比图
  renderRevenuePerPersonChart(lightingCompanies, audioCompanies)
  
  // 渲染DSO对比图
  renderDsoChart(lightingCompanies, audioCompanies)
  
  // 渲染DIO对比图
  renderDioChart(lightingCompanies, audioCompanies)
}

// 渲染收入对比图
const renderRevenueChart = (lightingCompanies: any[], audioCompanies: any[]) => {
  if (!revenueChart.value) return
  
  if (revenueChartInstance) {
    revenueChartInstance.dispose()
  }
  
  revenueChartInstance = echarts.init(revenueChart.value)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    legend: {
      data: ['收入']
    },
    xAxis: {
      type: 'category',
      data: lightingCompanies.map(item => companyNames[item.company_key as keyof typeof companyNames])
    },
    yAxis: {
      type: 'value',
      name: '收入',
      axisLabel: {
        formatter: (value: number) => formatCurrency(value, 'USD', companyStore.showUSD)
      }
    },
    series: [{
      name: '收入',
      type: 'bar',
      data: lightingCompanies.map(item => ({
        value: item.revenue,
        itemStyle: {
          color: item.revenue > 0 ? '#52c41a' : '#ff4d4f'
        }
      })),
      label: {
        show: true,
        position: 'top',
        formatter: (params: any) => formatCurrency(params.value, 'USD', companyStore.showUSD)
      }
    }]
  }
  
  revenueChartInstance.setOption(option)
}

// 渲染毛利率对比图
const renderGrossMarginChart = (lightingCompanies: any[], audioCompanies: any[]) => {
  if (!grossMarginChart.value) return
  
  if (grossMarginChartInstance) {
    grossMarginChartInstance.dispose()
  }
  
  grossMarginChartInstance = echarts.init(grossMarginChart.value)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        return `${params[0].name}<br/>毛利率: ${params[0].value.toFixed(1)}%`
      }
    },
    legend: {
      data: ['毛利率']
    },
    xAxis: {
      type: 'category',
      data: lightingCompanies.map(item => companyNames[item.company_key as keyof typeof companyNames])
    },
    yAxis: {
      type: 'value',
      name: '毛利率(%)',
      axisLabel: {
        formatter: '{value}%'
      }
    },
    series: [{
      name: '毛利率',
      type: 'bar',
      data: lightingCompanies.map(item => ({
        value: item.gross_margin * 100,
        itemStyle: {
          color: item.gross_margin > 0.3 ? '#52c41a' : 
                 item.gross_margin > 0.2 ? '#faad14' : '#ff4d4f'
        }
      })),
      label: {
        show: true,
        position: 'top',
        formatter: (params: any) => `${params.value.toFixed(1)}%`
      }
    }]
  }
  
  grossMarginChartInstance.setOption(option)
}

// 渲染净利率对比图
const renderNetMarginChart = (lightingCompanies: any[], audioCompanies: any[]) => {
  if (!netMarginChart.value) return
  
  if (netMarginChartInstance) {
    netMarginChartInstance.dispose()
  }
  
  netMarginChartInstance = echarts.init(netMarginChart.value)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        return `${params[0].name}<br/>净利率: ${params[0].value.toFixed(1)}%`
      }
    },
    legend: {
      data: ['净利率']
    },
    xAxis: {
      type: 'category',
      data: lightingCompanies.map(item => companyNames[item.company_key as keyof typeof companyNames])
    },
    yAxis: {
      type: 'value',
      name: '净利率(%)',
      axisLabel: {
        formatter: '{value}%'
      }
    },
    series: [{
      name: '净利率',
      type: 'bar',
      data: lightingCompanies.map(item => ({
        value: item.net_margin * 100,
        itemStyle: {
          color: item.net_margin > 0.15 ? '#52c41a' : 
                 item.net_margin > 0.1 ? '#faad14' : '#ff4d4f'
        }
      })),
      label: {
        show: true,
        position: 'top',
        formatter: (params: any) => `${params.value.toFixed(1)}%`
      }
    }]
  }
  
  netMarginChartInstance.setOption(option)
}

// 渲染人均产值对比图
const renderRevenuePerPersonChart = (lightingCompanies: any[], _audioCompanies: any[]) => {
  if (!revenuePerPersonChart.value) return
  
  if (revenuePerPersonChartInstance) {
    revenuePerPersonChartInstance.dispose()
  }
  
  revenuePerPersonChartInstance = echarts.init(revenuePerPersonChart.value)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        return `${params[0].name}<br/>人均产值: ${formatCurrency(params[0].value, 'USD')}`
      }
    },
    legend: {
      data: ['人均产值']
    },
    xAxis: {
      type: 'category',
      data: lightingCompanies.map(item => companyNames[item.company_key as keyof typeof companyNames])
    },
    yAxis: {
      type: 'value',
      name: '人均产值',
      axisLabel: {
        formatter: (value: number) => formatCurrency(value, 'USD')
      }
    },
    series: [{
      name: '人均产值',
      type: 'bar',
      data: lightingCompanies.map(item => ({
        value: item.revenue_per_person,
        itemStyle: {
          color: item.revenue_per_person > 50000 ? '#52c41a' : 
                 item.revenue_per_person > 30000 ? '#faad14' : '#ff4d4f'
        }
      })),
      label: {
        show: true,
        position: 'top',
        formatter: (params: any) => formatCurrency(params.value, 'USD')
      }
    }]
  }
  
  revenuePerPersonChartInstance.setOption(option)
}

// 渲染DSO对比图
const renderDsoChart = (lightingCompanies: any[], audioCompanies: any[]) => {
  if (!dsoChart.value) return
  
  if (dsoChartInstance) {
    dsoChartInstance.dispose()
  }
  
  dsoChartInstance = echarts.init(dsoChart.value)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        return `${params[0].name}<br/>DSO: ${params[0].value.toFixed(0)}天`
      }
    },
    legend: {
      data: ['DSO']
    },
    xAxis: {
      type: 'category',
      data: lightingCompanies.map(item => companyNames[item.company_key as keyof typeof companyNames])
    },
    yAxis: {
      type: 'value',
      name: 'DSO(天)',
      axisLabel: {
        formatter: '{value}天'
      }
    },
    series: [{
      name: 'DSO',
      type: 'bar',
      data: lightingCompanies.map(item => ({
        value: item.dso,
        itemStyle: {
          color: item.dso < 45 ? '#52c41a' : 
                 item.dso < 60 ? '#faad14' : '#ff4d4f'
        }
      })),
      label: {
        show: true,
        position: 'top',
        formatter: (params: any) => `${params.value.toFixed(0)}天`
      }
    }]
  }
  
  dsoChartInstance.setOption(option)
}

// 渲染DIO对比图
const renderDioChart = (lightingCompanies: any[], _audioCompanies: any[]) => {
  if (!dioChart.value) return
  
  if (dioChartInstance) {
    dioChartInstance.dispose()
  }
  
  dioChartInstance = echarts.init(dioChart.value)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        return `${params[0].name}<br/>DIO: ${params[0].value.toFixed(0)}天`
      }
    },
    legend: {
      data: ['DIO']
    },
    xAxis: {
      type: 'category',
      data: lightingCompanies.map(item => companyNames[item.company_key as keyof typeof companyNames])
    },
    yAxis: {
      type: 'value',
      name: 'DIO(天)',
      axisLabel: {
        formatter: '{value}天'
      }
    },
    series: [{
      name: 'DIO',
      type: 'bar',
      data: lightingCompanies.map(item => ({
        value: item.dio,
        itemStyle: {
          color: item.dio < 60 ? '#52c41a' : 
                 item.dio < 90 ? '#faad14' : '#ff4d4f'
        }
      })),
      label: {
        show: true,
        position: 'top',
        formatter: (params: any) => `${params.value.toFixed(0)}天`
      }
    }]
  }
  
  dioChartInstance.setOption(option)
}

// 窗口大小调整处理
const handleResize = () => {
  revenueChartInstance?.resize()
  grossMarginChartInstance?.resize()
  netMarginChartInstance?.resize()
  revenuePerPersonChartInstance?.resize()
  dsoChartInstance?.resize()
  dioChartInstance?.resize()
}

// 生命周期
onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})

// 监听 USD 切换
watch(() => companyStore.showUSD, () => {
  renderCharts()
})

// 组件卸载时清理
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  revenueChartInstance?.dispose()
  grossMarginChartInstance?.dispose()
  netMarginChartInstance?.dispose()
  revenuePerPersonChartInstance?.dispose()
  dsoChartInstance?.dispose()
  dioChartInstance?.dispose()
})
</script>

<style scoped lang="less">
.group-monthly {
  padding: 20px;
  background: #f5f5f5;
  min-height: 100vh;
}

.month-selector {
  background: white;
  padding: 16px 20px;
  margin-bottom: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 400px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.error-container {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.charts-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.chart-section {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  
  h3 {
    margin: 0 0 16px 0;
    color: #333;
    font-size: 16px;
    font-weight: 600;
  }
}

.chart {
  width: 100%;
  height: 300px;
}

// 响应式设计
@media (max-width: 768px) {
  .group-monthly {
    padding: 12px;
  }
  
  .month-selector {
    padding: 12px 16px;
  }
  
  .chart-section {
    padding: 16px;
  }
  
  .chart {
    height: 250px;
  }
}

@media (max-width: 480px) {
  .group-monthly {
    padding: 8px;
  }
  
  .month-selector {
    padding: 8px 12px;
  }
  
  .chart-section {
    padding: 12px;
  }
  
  .chart {
    height: 200px;
  }
}
</style>