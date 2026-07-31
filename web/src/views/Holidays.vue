<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  deletePastHolidays,
  getHolidays,
  saveHolidays,
  syncOfficialHolidays,
} from "../api/client";
import type { HolidayItem } from "../api/client";

const currentYear = Number(
  new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
  })
    .format(new Date())
    .replace(/\D/g, ""),
);
const syncYear = shallowRef(currentYear);
const officialUrl = shallowRef("");
const loading = shallowRef(false);
const saving = shallowRef(false);
const syncing = shallowRef(false);
const cleaning = shallowRef(false);
const items = ref<HolidayItem[]>([]);
const operationBusy = computed(
  () => loading.value || saving.value || syncing.value || cleaning.value,
);

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

async function confirmAction(message: string, title: string): Promise<boolean> {
  try {
    await ElMessageBox.confirm(message, title, {
      type: "warning",
      confirmButtonText: "确认",
      cancelButtonText: "取消",
    });
    return true;
  } catch {
    return false;
  }
}

async function onSyncOfficial() {
  const confirmed = await confirmAction(
    `将从国务院政策文件库查找并同步 ${syncYear.value} 年官方安排。`,
    `确认同步 ${syncYear.value} 年`,
  );
  if (!confirmed) return;

  syncing.value = true;
  try {
    const data = await syncOfficialHolidays(syncYear.value);
    items.value = data.items;
    officialUrl.value = data.source_url;
    ElMessage.success(`已同步 ${data.year} 年官方安排，共 ${data.count} 条`);
  } finally {
    syncing.value = false;
  }
}

async function onDeletePast() {
  const confirmed = await confirmAction(
    "将删除早于今天的全部节假日和调休上班日。",
    "确认清理已过期日期",
  );
  if (!confirmed) return;

  cleaning.value = true;
  try {
    const data = await deletePastHolidays();
    items.value = data.items;
    ElMessage.success(`已清理 ${data.deleted} 条过期日期`);
  } finally {
    cleaning.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page-card">
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px; gap: 12px; flex-wrap: wrap">
      <div>
        <h3 class="page-title" style="margin: 0 0 4px">节假日 & 调休上班日</h3>
        <el-link
          v-if="officialUrl"
          :href="officialUrl"
          target="_blank"
          rel="noopener noreferrer"
          type="primary"
        >
          查看刚同步的官方通知
        </el-link>
      </div>
      <div style="display: flex; gap: 8px; flex-wrap: wrap">
        <el-input-number
          v-model="syncYear"
          :min="2000"
          :max="2100"
          :step="1"
          :precision="0"
          controls-position="right"
          :disabled="operationBusy"
          style="width: 126px"
        />
        <el-button
          :loading="syncing"
          :disabled="operationBusy"
          @click="onSyncOfficial"
        >
          同步 {{ syncYear }} 年官方安排
        </el-button>
        <el-button
          type="danger"
          plain
          :loading="cleaning"
          :disabled="operationBusy"
          @click="onDeletePast"
        >
          一键清理已过期
        </el-button>
        <el-button
          type="primary"
          :loading="saving"
          :disabled="operationBusy"
          @click="onSaveAll"
        >
          保存全部
        </el-button>
      </div>
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

    <el-button
      style="margin-top: 16px"
      :disabled="operationBusy"
      @click="openAdd"
    >
      新增节假日
    </el-button>
  </div>
</template>
