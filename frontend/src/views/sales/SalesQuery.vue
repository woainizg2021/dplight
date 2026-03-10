<template>
  <div class="sales-query">
    <a-page-header title="销售查询 (Sales Query)" />
    <div class="content">
      <a-card>
        <a-tabs default-active-key="1">
          <a-tab-pane key="1" title="按客户 (By Customer)">
            <a-empty description="暂无数据" />
          </a-tab-pane>
          <a-tab-pane key="2" title="按单品 (By SKU)">
            <a-empty description="暂无数据" />
          </a-tab-pane>
          <a-tab-pane key="3" title="按业务员 (By Salesman)">
            <a-empty description="暂无数据" />
          </a-tab-pane>
        </a-tabs>
      </a-card>
    </div>
  </div>
</template>

<style scoped>
.sales-query {
  padding: 20px;
}
</style>
