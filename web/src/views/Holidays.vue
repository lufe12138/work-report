<script setup lang="ts">
import { onMounted, ref, shallowRef } from "vue";
import { ElMessage } from "element-plus";
import { getHolidays, saveHolidays } from "../api/client";
import type { HolidayItem } from "../api/client";

const loading = shallowRef(false);
const saving = shallowRef(false);
const items = ref<HolidayItem[]>([]);

async function load() {
  loading.value = true;
  try {
    const data = await getHolidays();
    items.value = data.items;
  } finally {
    loading.value = false;
  }
}

function openAdd() {
  items.value.unshift({ date: "", description: "", is_makeup: false });
}

function removeItem(index: number) {
  items.value.splice(index, 1);
}

function prepareItems(): HolidayItem[] | null {
  const cleaned = items.value.map((item) => ({
    date: item.date,
    description: item.description.trim(),
    is_makeup: item.is_makeup,
  }));
  const incompleteIndex = cleaned.findIndex((item) => !item.date || !item.description);
  if (incompleteIndex >= 0) {
    ElMessage.warning(`第 ${incompleteIndex + 1} 行的日期和描述不能为空`);
    return null;
  }
  const dates = cleaned.map((item) => item.date);
  if (new Set(dates).size !== dates.length) {
    ElMessage.warning("节假日日期不能重复");
    return null;
  }
  return cleaned;
}

async function onSaveAll() {
  const cleaned = prepareItems();
  if (cleaned === null) return;

  saving.value = true;
  try {
    const data = await saveHolidays(cleaned);
    items.value = data.items;
    ElMessage.success(`已保存 ${items.value.length} 条节假日`);
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page-card">
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px; gap: 12px; flex-wrap: wrap">
      <div>
        <h3 class="page-title" style="margin: 0 0 4px">节假日 & 调休上班日</h3>
        <div class="muted">维护 2026 年法定节假日和调休上班日（存储到 SQLite）</div>
      </div>
      <el-button type="primary" :loading="saving" @click="onSaveAll">保存全部</el-button>
    </div>

    <el-table :data="items" v-loading="loading" stripe empty-text="暂无节假日">
      <el-table-column label="日期" width="140">
        <template #default="{ row }">
          <el-input v-model="row.date" type="date" />
        </template>
      </el-table-column>
      <el-table-column label="描述" width="220">
        <template #default="{ row }">
          <el-input v-model="row.description" />
        </template>
      </el-table-column>
      <el-table-column label="调休上班" width="100">
        <template #default="{ row }">
          <el-checkbox v-model="row.is_makeup" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ $index }">
          <el-button link type="danger" @click="removeItem($index)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-button style="margin-top: 16px" @click="openAdd">新增节假日</el-button>
  </div>
</template>
