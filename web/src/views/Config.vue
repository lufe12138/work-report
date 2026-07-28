<template>
  <div class="page-card" v-loading="loading">
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px">
      <h3 class="page-title" style="margin: 0">系统配置</h3>
      <div style="display: flex; gap: 8px">
        <el-button @click="onTestDingtalk" :loading="testing">测试钉钉</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </div>
    </div>
    <p class="muted" style="margin-top: 0">
      密钥类字段已配置时显示脱敏值；留空保存表示不修改。配置保存在 SQLite，优先于仅作首次导入的 .env。
    </p>

    <el-form label-width="140px" style="max-width: 820px">
      <el-divider content-position="left">GitLab</el-divider>
      <el-form-item label="GitLab URL">
        <el-input v-model="form.gitlab_url" placeholder="http://gitlab.example.com" />
      </el-form-item>
      <el-form-item label="Token">
        <el-input
          v-model="form.gitlab_token"
          type="password"
          show-password
          :placeholder="secretPlaceholder('gitlab_token')"
        />
      </el-form-item>
      <el-form-item label="作者邮箱">
        <el-input v-model="form.author_email" />
      </el-form-item>
      <el-form-item label="项目 IDs">
        <el-input
          v-model="form.project_ids"
          type="textarea"
          :rows="2"
          placeholder="逗号分隔，如 353,352,350"
        />
      </el-form-item>

      <el-divider content-position="left">LLM</el-divider>
      <el-form-item label="API Key">
        <el-input
          v-model="form.llm_api_key"
          type="password"
          show-password
          :placeholder="secretPlaceholder('llm_api_key')"
        />
      </el-form-item>
      <el-form-item label="Base URL">
        <el-input v-model="form.llm_base_url" />
      </el-form-item>
      <el-form-item label="Model">
        <el-input v-model="form.llm_model" />
      </el-form-item>
      <el-form-item label="Timeout (秒)">
        <el-input v-model="form.llm_timeout" />
      </el-form-item>

      <el-divider content-position="left">钉钉</el-divider>
      <el-form-item label="Webhook">
        <el-input
          v-model="form.dingtalk_webhook"
          type="password"
          show-password
          :placeholder="secretPlaceholder('dingtalk_webhook')"
        />
      </el-form-item>
      <el-form-item label="加签 Secret">
        <el-input
          v-model="form.dingtalk_secret"
          type="password"
          show-password
          :placeholder="secretPlaceholder('dingtalk_secret')"
        />
      </el-form-item>
      <el-form-item label="Timeout (秒)">
        <el-input v-model="form.dingtalk_timeout" />
      </el-form-item>

      <el-divider content-position="left">其他</el-divider>
      <el-form-item label="时区偏移">
        <el-input v-model="form.timezone_offset_hours" placeholder="8" />
      </el-form-item>
      <el-form-item label="定时时间">
        <el-input v-model="form.schedule_time" placeholder="17:30" />
      </el-form-item>
      <el-form-item label="定时星期">
        <el-input v-model="form.schedule_days" placeholder="Mon,Tue,Wed,Thu,Fri" />
      </el-form-item>
      <p class="muted">
        定时时间/星期用于 Windows 计划任务脚本；修改后需重新运行
        scripts/install_scheduled_task.ps1。Web 端可随时手动触发运行。
      </p>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { getConfig, testDingtalk, updateConfig } from "../api/client";

const loading = ref(false);
const saving = ref(false);
const testing = ref(false);
const secrets = reactive<Record<string, { configured: boolean; masked: string }>>({});
const form = reactive<Record<string, string>>({
  gitlab_url: "",
  gitlab_token: "",
  author_email: "",
  project_ids: "",
  llm_api_key: "",
  llm_base_url: "",
  llm_model: "",
  llm_timeout: "",
  dingtalk_webhook: "",
  dingtalk_secret: "",
  dingtalk_timeout: "",
  timezone_offset_hours: "",
  schedule_time: "",
  schedule_days: "",
});

function secretPlaceholder(key: string) {
  const s = secrets[key];
  if (s?.configured) return `已配置 ${s.masked}，留空不修改`;
  return "未配置";
}

async function load() {
  loading.value = true;
  try {
    const data = await getConfig();
    for (const key of Object.keys(form)) {
      const val = data[key];
      if (val && typeof val === "object" && "configured" in val) {
        secrets[key] = val;
        form[key] = "";
      } else {
        form[key] = val ?? "";
      }
    }
  } finally {
    loading.value = false;
  }
}

async function onSave() {
  saving.value = true;
  try {
    const payload: Record<string, string> = {};
    for (const [k, v] of Object.entries(form)) {
      payload[k] = v;
    }
    await updateConfig(payload);
    ElMessage.success("配置已保存");
    await load();
  } finally {
    saving.value = false;
  }
}

async function onTestDingtalk() {
  testing.value = true;
  try {
    await testDingtalk();
    ElMessage.success("钉钉测试消息已发送");
  } finally {
    testing.value = false;
  }
}

onMounted(load);
</script>
