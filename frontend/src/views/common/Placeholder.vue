<template>
  <div class="placeholder-page">
    <a-result status="404" title="开发中 (Under Development)">
      <template #subtitle>
        该模块正在开发中，敬请期待...
      </template>
      <template #extra>
        <a-button type="primary" @click="$router.push('/')">返回首页</a-button>
      </template>
    </a-result>
  </div>
</template>

<style scoped>
.placeholder-page {
  padding: 40px;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
}
</style>
