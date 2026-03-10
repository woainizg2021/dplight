<template>
  <div class="container">
    <a-alert type="success">
      欢迎使用 Dplight ERP 新版系统 (Vue 3 + FastAPI)
    </a-alert>
    <div style="margin-top: 20px;">
        <a-card title="系统状态">
            <p>前端框架: Vue 3.3 + TypeScript</p>
            <p>UI组件库: Arco Design Vue</p>
            <p>后端服务: FastAPI (Port 8000)</p>
            <p>当前账套: {{ appStore.tenant }}</p>
            <p>货币显示: {{ appStore.showUSD ? 'USD' : 'Local Currency' }}</p>
        </a-card>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { useAppStore } from '../../stores/app';

const appStore = useAppStore();
</script>

<style scoped>
.container {
  padding: 20px;
}
</style>
