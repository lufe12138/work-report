<template>
  <div v-loading="loading">
    <div class="page-card" style="margin-bottom: 16px">
      <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap">
        <div>
          <h3 class="page-title" style="margin-bottom: 8px">
            运行 #{{ detail?.id }}
            <StatusTag v-if="detail" :status="detail.status" style="margin-left: 8px" />
          </h3>
          <div class="muted">
            触发：{{ detail?.trigger || "-" }} ·
            创建：{{ detail?.created_at || "-" }} ·
            完成：{{ detail?.finished_at || "-" }}
          </div>
        </div>
        <el-button @click="$router.push('/runs')">返回列表</el-button>
      </div>

      <el-descriptions :column="2" border style="margin-top: 16px">
        <el-descriptions-item label="时间范围">
          <span v-if="detail?.week_start">{{ detail.week_start }} ~ {{ detail.week_end }}</span>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="提交 / 项目">
          {{ detail?.total_commits ?? 0 }} / {{ detail?.project_count ?? 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="钉钉">
          <el-tag v-if="detail?.dingtalk_sent" type="success" size="small">已发送</el-tag>
          <span v-else>未发送</span>
          <span v-if="detail?.dingtalk_error" style="color: #f56c6c; margin-left: 8px">
            {{ detail.dingtalk_error }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="错误">
          {{ detail?.error_message || "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="节假日判断" :span="2">
          {{ detail?.holiday_reason || "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="选项" :span="2">
          <code>{{ JSON.stringify(detail?.options || {}) }}</code>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="page-card">
      <el-tabs v-model="tab">
        <el-tab-pane label="周报正文" name="report">
          <div style="display: flex; justify-content: flex-end; margin-bottom: 8px">
            <el-button size="small" @click="copyReport">复制</el-button>
          </div>
          <pre class="mono report-box">{{ detail?.report_text || "（暂无）" }}</pre>
        </el-tab-pane>
        <el-tab-pane :label="`提交记录 (${commits.length})`" name="commits">
          <el-table :data="commits" stripe empty-text="无提交" max-height="520">
            <el-table-column prop="project_name" label="项目" min-width="160" />
            <el-table-column prop="short_id" label="Short ID" width="100" />
            <el-table-column prop="title" label="标题" min-width="240" />
            <el-table-column prop="author_name" label="作者" width="120" />
            <el-table-column prop="created_at" label="时间" min-width="170" />
          </el-table>
        </el-tab-pane>
        <el-tab-pane :label="`日志 (${logs.length})`" name="logs">
          <el-timeline style="padding-left: 4px">
            <el-timeline-item
              v-for="log in logs"
              :key="log.id"
              :type="logType(log.level)"
              :timestamp="log.created_at"
              placement="top"
            >
              <el-tag size="small" style="margin-right: 8px">{{ log.level }}</el-tag>
              {{ log.message }}
            </el-timeline-item>
          </el-timeline>
          <div v-if="!logs.length" class="muted">暂无日志</div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { getRun } from "../api/client";
import StatusTag from "../components/StatusTag.vue";

const props = defineProps<{ id: string }>();
const loading = ref(false);
const detail = ref<any>(null);
const tab = ref("report");
let timer: number | undefined;

const commits = computed(() => detail.value?.commits || []);
const logs = computed(() => detail.value?.logs || []);

function logType(level: string) {
  if (level === "ERROR") return "danger";
  if (level === "WARNING") return "warning";
  return "primary";
}

async function load() {
  loading.value = !detail.value;
  try {
    detail.value = await getRun(props.id);
  } finally {
    loading.value = false;
  }
}

async function copyReport() {
  const text = detail.value?.report_text || "";
  if (!text) {
    ElMessage.warning("无内容可复制");
    return;
  }
  await navigator.clipboard.writeText(text);
  ElMessage.success("已复制周报正文");
}

onMounted(() => {
  load();
  timer = window.setInterval(() => {
    if (["pending", "running"].includes(detail.value?.status)) {
      load();
    }
  }, 2500);
});
onUnmounted(() => {
  if (timer) window.clearInterval(timer);
});
</script>

<style scoped>
.report-box {
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  max-height: 560px;
  overflow: auto;
  margin: 0;
}
</style>
