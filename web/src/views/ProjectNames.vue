<template>
  <div class="page-card">
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px; gap: 12px; flex-wrap: wrap">
      <div>
        <h3 class="page-title" style="margin: 0 0 4px">项目中文名映射</h3>
        <div class="muted">GitLab 项目名 → 周报展示中文名（后处理会强制校正）</div>
      </div>
      <div style="display: flex; gap: 8px">
        <el-button @click="openAdd">新增</el-button>
        <el-button type="primary" :loading="saving" @click="onSaveAll">保存全部</el-button>
      </div>
    </div>

    <el-table :data="items" v-loading="loading" stripe empty-text="暂无映射">
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
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { getProjectNames, saveProjectNames } from "../api/client";

const loading = ref(false);
const saving = ref(false);
const items = ref<{ project_key: string; display_name: string }[]>([]);

async function load() {
  loading.value = true;
  try {
    const data = await getProjectNames();
    items.value = (data.items || []).map((i: any) => ({ ...i }));
  } finally {
    loading.value = false;
  }
}

function openAdd() {
  items.value.unshift({ project_key: "", display_name: "" });
}

async function onSaveAll() {
  const cleaned = items.value
    .map((i) => ({
      project_key: i.project_key.trim(),
      display_name: i.display_name.trim(),
    }))
    .filter((i) => i.project_key && i.display_name);
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
