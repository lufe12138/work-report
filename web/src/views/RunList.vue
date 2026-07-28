<template>
  <div class="page-card">
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px; gap: 12px">
      <h3 class="page-title" style="margin: 0">运行记录</h3>
      <div style="display: flex; gap: 8px">
        <el-select v-model="status" clearable placeholder="状态筛选" style="width: 140px" @change="load">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
          <el-option label="运行中" value="running" />
          <el-option label="跳过" value="skipped" />
          <el-option label="等待" value="pending" />
        </el-select>
        <el-button @click="load">刷新</el-button>
      </div>
    </div>

    <el-table :data="items" v-loading="loading" stripe empty-text="暂无记录">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="status" label="状态" width="110">
        <template #default="{ row }">
          <StatusTag :status="row.status" />
        </template>
      </el-table-column>
      <el-table-column prop="trigger" label="触发" width="90" />
      <el-table-column prop="total_commits" label="提交" width="80" />
      <el-table-column prop="project_count" label="项目" width="80" />
      <el-table-column label="钉钉" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.dingtalk_sent" type="success" size="small">已发</el-tag>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="时间范围" min-width="220">
        <template #default="{ row }">
          <span v-if="row.week_start">{{ row.week_start }} ~ {{ row.week_end }}</span>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" min-width="160" />
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="$router.push(`/runs/${row.id}`)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="margin-top: 16px; display: flex; justify-content: flex-end">
      <el-pagination
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="size"
        :current-page="page"
        @current-change="onPage"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { listRuns } from "../api/client";
import StatusTag from "../components/StatusTag.vue";

const loading = ref(false);
const items = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const size = ref(20);
const status = ref<string | undefined>();

async function load() {
  loading.value = true;
  try {
    const data = await listRuns({
      page: page.value,
      size: size.value,
      status: status.value || undefined,
    });
    items.value = data.items || [];
    total.value = data.total || 0;
  } finally {
    loading.value = false;
  }
}

function onPage(p: number) {
  page.value = p;
  load();
}

onMounted(load);
</script>
