<template>
  <div ref="chartRef" :style="{ width: width, height: height }"></div>
</template>

<script lang="ts" setup>
import { ref, onMounted, watch, onUnmounted, shallowRef } from 'vue';
import * as echarts from 'echarts';

const props = defineProps({
  width: {
    type: String,
    default: '100%'
  },
  height: {
    type: String,
    default: '400px'
  },
  option: {
    type: Object,
    required: true
  },
  theme: {
    type: String,
    default: 'default'
  }
});

const chartRef = ref<HTMLElement | null>(null);
const chartInstance = shallowRef<echarts.ECharts | null>(null);

// Global theme colors
const colors = ['#2E75B6', '#ED7D31', '#70AD47', '#C00000', '#FFC000'];

const initChart = () => {
  if (chartRef.value) {
    chartInstance.value = echarts.init(chartRef.value, props.theme);
    // Merge default color palette
    const finalOption = {
      color: colors,
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      ...props.option
    };
    chartInstance.value.setOption(finalOption);
    
    window.addEventListener('resize', resizeHandler);
  }
};

const resizeHandler = () => {
  chartInstance.value?.resize();
};

watch(() => props.option, (newOption) => {
  if (chartInstance.value) {
    chartInstance.value.setOption({
        color: colors,
        ...newOption
    }, true); // not merge
  }
}, { deep: true });

onMounted(() => {
  initChart();
});

onUnmounted(() => {
  window.removeEventListener('resize', resizeHandler);
  chartInstance.value?.dispose();
});
</script>
