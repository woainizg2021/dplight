<template>
  <div class="sales-performance">
    <a-page-header title="五司销售绩效看板 (Sales Performance Dashboard)" />
    
    <!-- 筛选器 -->
    <div class="filters">
      <a-space>
        <span>时间维度：</span>
        <a-radio-group v-model="timeDimension" @change="handleTimeDimensionChange">
          <a-radio value="year">年度</a-radio>
          <a-radio value="quarter">季度</a-radio>
          <a-radio value="month">月度</a-radio>
        </a-radio-group>
        
        <span>选择时间：</span>
        <a-date-picker 
          v-model="selectedDate" 
          :mode="datePickerMode"
          :format="dateFormat"
          @change="handleDateChange"
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

    <!-- 绩效表格 -->
    <div v-else class="performance-container">
      <div class="performance-table">
        <a-table 
          :columns="columns" 
          :data="performanceData"
          :pagination="false"
          :scroll="{ x: 1000 }"
        >
          <template #company_name="{ record }">
            <div class="company-name">
              <span class="flag">{{ getCompanyFlag(record.company_key) }}</span>
              <span>{{ getCompanyShortName(record.company_key) }}</span>
            </div>
          </template>
          
          <template #target="{ record }">
            <div class="target-cell">
              <span>{{ formatCurrency(record.target, record.currency, companyStore.showUSD) }}</span>
            </div>
          </template>
          
          <template #actual="{ record }">
            <div class="actual-cell">
              <span>{{ formatCurrency(record.actual, record.currency, companyStore.showUSD) }}</span>
            </div>
          </template>
          
          <template #completion_rate="{ record }">
            <div class="completion-rate-cell">
              <a-progress 
                :percent="record.completion_rate * 100" 
                :status="getProgressStatus(record.completion_rate)"
                :show-text="false"
              />
              <span class="rate-text">{{ (record.completion_rate * 100).toFixed(1) }}%</span>
            </div>
          </template>
          
          <template #yoy="{ record }">
            <div class="growth-cell" :class="getGrowthClass(record.yoy)">
              <span>{{ (record.yoy * 100).toFixed(1) }}%</span>
              <icon-arrow-up v-if="record.yoy > 0" />
              <icon-arrow-down v-else-if="record.yoy < 0" />
            </div>
          </template>
          
          <template #mom="{ record }">
            <div class="growth-cell" :class="getGrowthClass(record.mom)">
              <span>{{ (record.mom * 100).toFixed(1) }}%</span>
              <icon-arrow-up v-if="record.mom > 0" />
              <icon-arrow-down v-else-if="record.mom < 0" />
            </div>
          </template>
        </a-table>
      </div>

      <!-- 图表分析 -->
      <div class="charts-section">
        <a-row :gutter="16">
          <a-col :span="12">
            <div class="chart-card">
              <h4>目标完成率对比</h4>
              <div ref="completionChart" class="chart"></div>
            </div>
          </a-col>
          <a-col :span="12">
            <div class="chart-card">
              <h4>同比增长对比</h4>
              <div ref="yoyChart" class="chart"></div>
            </div>
          </a-col>
        </a-row>
        
        <a-row :gutter="16" style="margin-top: 16px;">
          <a-col :span="12">
            <div class="chart-card">
              <h4>环比增长对比</h4>
              <div ref="momChart" class="chart"></div>
            </div>
          </a-col>
          <a-col :span="12">
            <div class="chart-card">
              <h4>销售规模对比</h4>
              <div ref="scaleChart" class="chart"></div>
            </div>
          </a-col>
        </a-row>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, computed, watch, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { getCurrentInstance } from 'vue'
import { useCompanyStore } from '@/stores/company'
import { formatCurrency } from '@/utils/formatter'

const { proxy } = getCurrentInstance() as any
const companyStore = useCompanyStore()

// 状态
const loading = ref(false)
const error = ref('')
const timeDimension = ref('month')
const selectedDate = ref(new Date())
const performanceData = ref<any[]>([])

// 图表实例
const completionChart = ref<HTMLElement>()
const yoyChart = ref<HTMLElement>()
const momChart = ref<HTMLElement>()
const scaleChart = ref<HTMLElement>()

let completionChartInstance: echarts.ECharts | null = null
let yoyChartInstance: echarts.ECharts | null = null
let momChartInstance: echarts.ECharts | null = null
let scaleChartInstance: echarts.ECharts | null = null

// 公司名称映射
const companyNames = {
  UGANDA: '乌干达',
  NIGERIA: '尼日利亚', 
  KENYA: '肯尼亚',
  KENYA_AUDIO: '肯尼亚音箱',
  DRC: '刚果金'
}

const companyFlags = {
  UGANDA: '🇺🇬',
  NIGERIA: '🇳🇬',
  KENYA: '🇰🇪',
  KENYA_AUDIO: '🔊',
  DRC: '🇨🇩'
}

// 表格列定义
const columns = [
  {
    title: '公司',
    dataIndex: 'company_name',
    slotName: 'company_name',
    width: 120,
    fixed: 'left'
  },
  {
    title: '目标',
    dataIndex: 'target',
    slotName: 'target',
    width: 120,
    align: 'right'
  },
  {
    title: '实际',
    dataIndex: 'actual',
    slotName: 'actual',
    width: 120,
    align: 'right'
  },
  {
    title: '完成率',
    dataIndex: 'completion_rate',
    slotName: 'completion_rate',
    width: 150,
    align: 'center'
  },
  {
    title: '同比增长',
    dataIndex: 'yoy',
    slotName: 'yoy',
    width: 120,
    align: 'center'
  },
  {
    title: '环比增长',
    dataIndex: 'mom',
    slotName: 'mom',
    width: 120,
    align: 'center'
  }
]

// 计算属性
const datePickerMode = computed(() => {
  switch (timeDimension.value) {
    case 'year': return 'year'
    case 'quarter': return 'quarter'
    case 'month': return 'month'
    default: return 'month'
  }
})

const dateFormat = computed(() => {
  switch (timeDimension.value) {
    case 'year': return 'YYYY年'
    case 'quarter': return 'YYYY年Q季度'
    case 'month': return 'YYYY年MM月'
    default: return 'YYYY年MM月'
  }
})

// 辅助函数
const getCompanyShortName = (key: string) => {
  return companyNames[key as keyof typeof companyNames] || key
}

const getCompanyFlag = (key: string) => {
  return companyFlags[key as keyof typeof companyFlags] || '🏢'
}

const getProgressStatus = (rate: number) => {
  if (rate >= 1) return 'success'
  if (rate >= 0.8) return 'warning'
  return 'danger'
}

const getGrowthClass = (growth: number) => {
  if (growth > 0) return 'positive'
  if (growth < 0) return 'negative'
  return 'neutral'
}

// 加载数据
const loadData = async () => {
  loading.value = true
  error.value = ''
  
  try {
    const year = selectedDate.value.getFullYear()
    const month = selectedDate.value.getMonth() + 1
    const quarter = Math.ceil(month / 3)
    
    const params = {
      year,
      month: timeDimension.value === 'month' ? month : undefined,
      quarter: timeDimension.value === 'quarter' ? quarter : undefined
    }
    
    const response = await proxy?.$api.get('/dashboard/sales-performance', { params })
    
    if (response.data) {
      performanceData.value = response.data.data.map((item: any) => ({
        ...item,
        company_name: getCompanyShortName(item.company_key)
      }))
      
      await nextTick()
      renderCharts()
    }
  } catch (err: any) {
    error.value = err.message || '加载数据失败'
  } finally {
    loading.value = false
  }
}

// 时间维度变更
const handleTimeDimensionChange = () => {
  // 重置日期选择器到当前时间
  selectedDate.value = new Date()
  loadData()
}

// 日期变更
const handleDateChange = () => {
  loadData()
}

// 渲染图表
const renderCharts = () => {
  if (!performanceData.value.length) return

  // 分离灯具厂和音箱厂数据
  const lightingCompanies = performanceData.value.filter(item => 
    item.company_key !== 'KENYA_AUDIO'
  )
  const audioCompanies = performanceData.value.filter(item => 
    item.company_key === 'KENYA_AUDIO'
  )

  renderCompletionChart(lightingCompanies, audioCompanies)
  renderYoyChart(lightingCompanies, audioCompanies)
  renderMomChart(lightingCompanies, audioCompanies)
  renderScaleChart(lightingCompanies, audioCompanies)
}

// 渲染完成率图表
const renderCompletionChart = (lightingCompanies: any[], _audioCompanies: any[]) => {
  if (!completionChart.value) return
  
  if (completionChartInstance) {
    completionChartInstance.dispose()
  }
  
  completionChartInstance = echarts.init(completionChart.value)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        return `${params[0].name}<br/>完成率: ${params[0].value.toFixed(1)}%`
      }
    },
    legend: {
      data: ['完成率']
    },
    xAxis: {
      type: 'category',
      data: lightingCompanies.map(item => getCompanyShortName(item.company_key))
    },
    yAxis: {
      type: 'value',
      name: '完成率(%)',
      axisLabel: {
        formatter: '{value}%'
      }
    },
    series: [{
      name: '完成率',
      type: 'bar',
      data: lightingCompanies.map(item => ({
        value: item.completion_rate * 100,
        itemStyle: {
          color: item.completion_rate >= 1 ? '#52c41a' : 
                 item.completion_rate >= 0.8 ? '#faad14' : '#ff4d4f'
        }
      })),
      label: {
        show: true,
        position: 'top',
        formatter: (params: any) => `${params.value.toFixed(1)}%`
      }
    }]
  }
  
  completionChartInstance.setOption(option)
}

// 渲染同比增长图表
const renderYoyChart = (lightingCompanies: any[], audioCompanies: any[]) => {
  if (!yoyChart.value) return
  
  if (yoyChartInstance) {
    yoyChartInstance.dispose()
  }
  
  yoyChartInstance = echarts.init(yoyChart.value)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        return `${params[0].name}<br/>同比增长: ${params[0].value.toFixed(1)}%`
      }
    },
    legend: {
      data: ['同比增长']
    },
    xAxis: {
      type: 'category',
      data: lightingCompanies.map(item => getCompanyShortName(item.company_key))
    },
    yAxis: {
      type: 'value',
      name: '同比增长(%)',
      axisLabel: {
        formatter: '{value}%'
      }
    },
    series: [{
      name: '同比增长',
      type: 'bar',
      data: lightingCompanies.map(item => ({
        value: item.yoy * 100,
        itemStyle: {
          color: item.yoy > 0 ? '#52c41a' : 
                 item.yoy < 0 ? '#ff4d4f' : '#999999'
        }
      })),
      label: {
        show: true,
        position: 'top',
        formatter: (params: any) => `${params.value.toFixed(1)}%`
      }
    }]
  }
  
  yoyChartInstance.setOption(option)
}

// 渲染环比增长图表
const renderMomChart = (lightingCompanies: any[], audioCompanies: any[]) => {
  if (!momChart.value) return
  
  if (momChartInstance) {
    momChartInstance.dispose()
  }
  
  momChartInstance = echarts.init(momChart.value)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        return `${params[0].name}<br/>环比增长: ${params[0].value.toFixed(1)}%`
      }
    },
    legend: {
      data: ['环比增长']
    },
    xAxis: {
      type: 'category',
      data: lightingCompanies.map(item => getCompanyShortName(item.company_key))
    },
    yAxis: {
      type: 'value',
      name: '环比增长(%)',
      axisLabel: {
        formatter: '{value}%'
      }
    },
    series: [{
      name: '环比增长',
      type: 'bar',
      data: lightingCompanies.map(item => ({
        value: item.mom * 100,
        itemStyle: {
          color: item.mom > 0 ? '#52c41a' : 
                 item.mom < 0 ? '#ff4d4f' : '#999999'
        }
      })),
      label: {
        show: true,
        position: 'top',
        formatter: (params: any) => `${params.value.toFixed(1)}%`
      }
    }]
  }
  
  momChartInstance.setOption(option)
}

// 渲染销售规模图表
const renderScaleChart = (lightingCompanies: any[], audioCompanies: any[]) => {
  if (!scaleChart.value) return
  
  if (scaleChartInstance) {
    scaleChartInstance.dispose()
  }
  
  scaleChartInstance = echarts.init(scaleChart.value)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        return `${params[0].name}<br/>实际销售: ${formatCurrency(params[0].value, 'USD')}`
      }
    },
    legend: {
      data: ['实际销售']
    },
    xAxis: {
      type: 'category',
      data: lightingCompanies.map(item => getCompanyShortName(item.company_key))
    },
    yAxis: {
      type: 'value',
      name: '销售金额',
      axisLabel: {
        formatter: (value: number) => formatCurrency(value, 'USD')
      }
    },
    series: [{
      name: '实际销售',
      type: 'bar',
      data: lightingCompanies.map(item => ({
        value: item.actual,
        itemStyle: {
          color: '#1890ff'
        }
      })),
      label: {
        show: true,
        position: 'top',
        formatter: (params: any) => formatCurrency(params.value, 'USD')
      }
    }]
  }
  
  scaleChartInstance.setOption(option)
}

// 监听 USD 切换
watch(() => companyStore.showUSD, () => {
  renderCharts()
})

// 窗口大小调整处理
const handleResize = () => {
  completionChartInstance?.resize()
  yoyChartInstance?.resize()
  momChartInstance?.resize()
  scaleChartInstance?.resize()
}

// 生命周期
onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})

// 组件卸载时清理
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  completionChartInstance?.dispose()
  yoyChartInstance?.dispose()
  momChartInstance?.dispose()
  scaleChartInstance?.dispose()
})
</script>

<style scoped lang="less">
.sales-performance {
  padding: 20px;
  background: #f5f5f5;
  min-height: 100vh;
}

.filters {
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

.performance-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.performance-table {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.company-name {
  display: flex;
  align-items: center;
  gap: 8px;
  
  .flag {
    font-size: 16px;
  }
}

.target-cell, .actual-cell {
  font-weight: 600;
  color: #333;
}

.completion-rate-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  
  .rate-text {
    font-size: 12px;
    font-weight: 600;
  }
}

.growth-cell {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 600;
  
  &.positive {
    color: #52c41a;
  }
  
  &.negative {
    color: #ff4d4f;
  }
  
  &.neutral {
    color: #999999;
  }
}

.charts-section {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.chart-card {
  background: #f8f9fa;
  padding: 16px;
  border-radius: 6px;
  
  h4 {
    margin: 0 0 12px 0;
    color: #333;
    font-size: 14px;
    font-weight: 600;
  }
}

.chart {
  width: 100%;
  height: 200px;
}

// 响应式设计
@media (max-width: 768px) {
  .sales-performance {
    padding: 12px;
  }
  
  .filters {
    padding: 12px 16px;
  }
  
  .performance-table, .charts-section {
    padding: 16px;
  }
  
  .chart-card {
    padding: 12px;
  }
  
  .chart {
    height: 150px;
  }
}

@media (max-width: 480px) {
  .sales-performance {
    padding: 8px;
  }
  
  .filters {
    padding: 8px 12px;
  }
  
  .performance-table, .charts-section {
    padding: 12px;
  }
  
  .chart-card {
    padding: 8px;
  }
  
  .chart {
    height: 120px;
  }
}
</style>