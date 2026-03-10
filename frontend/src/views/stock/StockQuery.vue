<template>
  <div class="stock-query">
    <a-page-header title="库存查询 (Stock Query)" />
    <div class="content">
      <a-card>
        <a-tabs default-active-key="1">
          <a-tab-pane key="1" title="成品库存 (Finished Goods)">
             <a-empty description="暂无数据" />
          </a-tab-pane>
          <a-tab-pane key="2" title="原材料 (Raw Material)">
             <a-empty description="暂无数据" />
          </a-tab-pane>
        </a-tabs>
      </a-card>
    </div>
  </div>
</template>

<style scoped>
.stock-query {
  padding: 20px;
}
</style>
