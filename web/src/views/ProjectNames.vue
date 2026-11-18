<template>
  <div class="page-card">
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px; gap: 12px; flex-wrap: wrap">
      <div>
        <h3 class="page-title" style="margin: 0 0 4px">项目名称与 ID</h3>
        <div class="muted">配置 GitLab 项目 ID 后，周报将按这些 ID 获取提交；项目名用于匹配展示名称。</div>
      </div>
      <div style="display: flex; gap: 8px">
        <el-button @click="openAdd">新增</el-button>
        <el-button type="primary" :loading="saving" @click="onSaveAll">保存全部</el-button>
      </div>
    </div>

    <div class="project-table-wrap">
      <el-table :data="items" v-loading="loading" stripe empty-text="暂无项目" class="project-table">
        <el-table-column label="项目 ID" width="170">
          <template #default="{ row }">
            <el-input-number
              v-model="row.project_id"
              :min="1"
              :step="1"
              :controls="false"
              placeholder="必填"
            />
          </template>
        </el-table-column>
        <el-table-column label="GitLab 项目名" min-width="220">
          <template #default="{ row }">
            <el-input v-model="row.project_key" />
          </template>
        </el-table-column>
        <el-table-column label="中文名" min-width="220">
          <template #default="{ row }">
            <el-input v-model="row.display_name" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ $index }">
            <el-button link type="danger" @click="items.splice($index, 1)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { getProjectNames, saveProjectNames } from "../api/client";

const loading = ref(false);
const saving = ref(false);
const items = ref<
  { project_id: number | null; project_key: string; display_name: string }[]
>([]);

async function load() {
  loading.value = true;
  try {
    const data = await getProjectNames();
    items.value = (data.items || []).map((i: any) => ({
      project_id: i.project_id ?? null,
      project_key: i.project_key || "",
      display_name: i.display_name || "",
    }));
  } finally {
    loading.value = false;
  }
}

function openAdd() {
  items.value.unshift({ project_id: null, project_key: "", display_name: "" });
}

async function onSaveAll() {
  const cleaned = items.value
    .map((i) => ({
      project_id: i.project_id,
      project_key: i.project_key.trim(),
      display_name: i.display_name.trim(),
    }))
    .filter((i) => i.project_key && i.display_name);
  const projectIds = cleaned
    .map((item) => item.project_id)
    .filter((projectId): projectId is number => projectId !== null);
  if (new Set(projectIds).size !== projectIds.length) {
    ElMessage.warning("项目 ID 不能重复");
    return;
  }
  saving.value = true;
  try {
    const data = await saveProjectNames(cleaned);
    items.value = data.items || cleaned;
    ElMessage.success(`已保存 ${items.value.length} 条映射`);
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.project-table {
  min-width: 760px;
}

.project-table :deep(.el-input-number) {
  width: 140px;
}

.project-table-wrap {
  overflow-x: auto;
}
</style>
