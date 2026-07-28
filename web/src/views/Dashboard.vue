<template>
  <div>
    <div class="stat-grid">
      <div class="stat-card">
        <div class="label">总运行次数</div>
        <div class="value">{{ data.total_runs ?? "-" }}</div>
      </div>
      <div class="stat-card">
        <div class="label">成功</div>
        <div class="value" style="color: #67c23a">{{ data.success_runs ?? "-" }}</div>
      </div>
      <div class="stat-card">
        <div class="label">失败</div>
        <div class="value" style="color: #f56c6c">{{ data.failed_runs ?? "-" }}</div>
      </div>
      <div class="stat-card">
        <div class="label">配置状态</div>
        <div class="value" style="font-size: 18px">
          <el-tag :type="data.config_ready ? 'success' : 'warning'">
            {{ data.config_ready ? "已就绪" : "待完善" }}
          </el-tag>
        </div>
      </div>
    </div>

    <div class="page-card" style="margin-bottom: 16px">
      <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap">
        <div>
          <h3 class="page-title" style="margin-bottom: 8px">立即生成周报</h3>
          <div class="muted">
            节假日：
            <template v-if="data.holiday">
              {{ data.holiday.reason || "-" }}
            </template>
            <template v-else>-</template>
          </div>
        </div>
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap">
          <el-checkbox v-model="opts.send_dingtalk">发送钉钉</el-checkbox>
          <el-checkbox v-model="opts.skip_llm">跳过 LLM</el-checkbox>
          <el-checkbox v-model="opts.if_last_workday">仅放假前最后工作日</el-checkbox>
          <el-button type="primary" :loading="starting || data.busy" @click="onStart">
            {{ data.busy ? "运行中…" : "开始运行" }}
          </el-button>
        </div>
      </div>
    </div>

    <div class="page-card">
      <h3 class="page-title">最近运行</h3>
      <el-table :data="data.recent || []" stripe empty-text="暂无记录">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <StatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column prop="trigger" label="触发" width="90" />
        <el-table-column prop="total_commits" label="提交数" width="90" />
        <el-table-column label="时间范围" min-width="200">
          <template #default="{ row }">
            <span v-if="row.week_start">{{ row.week_start }} ~ {{ row.week_end }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="160" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(`/runs/${row.id}`)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { createRun, getDashboard } from "../api/client";
import StatusTag from "../components/StatusTag.vue";

const router = useRouter();
const data = ref<Record<string, any>>({});
const starting = ref(false);
const opts = reactive({
  send_dingtalk: true,
  skip_llm: false,
  if_last_workday: false,
});
let timer: number | undefined;

async function load() {
  data.value = await getDashboard();
}

async function onStart() {
  starting.value = true;
  try {
    const res = await createRun({ ...opts });
    ElMessage.success(`任务已提交 #${res.id}`);
    router.push(`/runs/${res.id}`);
  } finally {
    starting.value = false;
  }
}

onMounted(() => {
  load();
  timer = window.setInterval(load, 5000);
});
onUnmounted(() => {
  if (timer) window.clearInterval(timer);
});
</script>
