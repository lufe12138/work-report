<template>
  <el-tag :type="type" effect="light">{{ label }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ status: string }>();

const map: Record<string, { type: string; label: string }> = {
  pending: { type: "info", label: "等待中" },
  running: { type: "warning", label: "运行中" },
  success: { type: "success", label: "成功" },
  failed: { type: "danger", label: "失败" },
  skipped: { type: "info", label: "已跳过" },
};

const type = computed(() => (map[props.status]?.type as any) || "info");
const label = computed(() => map[props.status]?.label || props.status);
</script>
