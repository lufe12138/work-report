<script setup lang="ts">
import { onMounted, reactive, shallowRef } from "vue";
import { ElMessage } from "element-plus";
import { getConfig, testDingtalk, testLlm, updateConfig } from "../api/client";
import MarkdownPromptEditor from "../components/config/MarkdownPromptEditor.vue";

interface ConfigForm {
  gitlab_url: string;
  gitlab_token: string;
  author_email: string;
  project_ids: string;
  llm_api_key: string;
  llm_base_url: string;
  llm_model: string;
  llm_timeout: string;
  llm_system_prompt: string;
  dingtalk_webhook: string;
  dingtalk_secret: string;
  dingtalk_timeout: string;
  timezone_offset_hours: string;
  schedule_time: string;
  schedule_days: string;
}

const loading = shallowRef(false);
const saving = shallowRef(false);
const testingLlm = shallowRef(false);
const testingDingtalk = shallowRef(false);
const secrets = reactive<Record<string, { configured: boolean; masked: string }>>({});
const form = reactive<ConfigForm>({
  gitlab_url: "",
  gitlab_token: "",
  author_email: "",
  project_ids: "",
  llm_api_key: "",
  llm_base_url: "",
  llm_model: "",
  llm_timeout: "",
  llm_system_prompt: "",
  dingtalk_webhook: "",
  dingtalk_secret: "",
  dingtalk_timeout: "",
  timezone_offset_hours: "",
  schedule_time: "",
  schedule_days: "",
});

function secretPlaceholder(key: string) {
  const secret = secrets[key];
  if (secret?.configured) return `已配置 ${secret.masked}，留空不修改`;
  return "未配置";
}

async function load() {
  loading.value = true;
  try {
    const data = await getConfig();
    for (const key of Object.keys(form) as Array<keyof ConfigForm>) {
      const value = data[key];
      if (value && typeof value === "object" && "configured" in value) {
        secrets[key] = value;
        form[key] = "";
      } else {
        form[key] = String(value ?? "");
      }
    }
  } finally {
    loading.value = false;
  }
}

async function onSave() {
  if (!form.llm_system_prompt.trim()) {
    ElMessage.warning("周报提示词不能为空");
    return;
  }

  saving.value = true;
  try {
    await updateConfig({ ...form });
    ElMessage.success("配置已保存");
    await load();
  } finally {
    saving.value = false;
  }
}

async function onTestLlm() {
  testingLlm.value = true;
  try {
    const data = await testLlm();
    ElMessage.success(`LLM 测活成功（${data.model}）：${data.reply}`);
  } finally {
    testingLlm.value = false;
  }
}

async function onTestDingtalk() {
  testingDingtalk.value = true;
  try {
    await testDingtalk();
    ElMessage.success("钉钉测试消息已发送");
  } finally {
    testingDingtalk.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="page-card" v-loading="loading">
    <div class="config-header">
      <h3 class="page-title config-title">系统配置</h3>
      <div class="config-actions">
        <el-button :loading="testingLlm" @click="onTestLlm">测试 LLM</el-button>
        <el-button :loading="testingDingtalk" @click="onTestDingtalk">
          测试钉钉
        </el-button>
        <el-button type="primary" :loading="saving" @click="onSave">
          保存
        </el-button>
      </div>
    </div>
    <p class="muted config-note">
      密钥类字段已配置时显示脱敏值；留空保存表示不修改。配置保存在 SQLite，优先于仅作首次导入的 .env。
    </p>

    <el-form label-width="140px" class="config-form">
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
      <el-form-item label="周报提示词" class="prompt-form-item">
        <MarkdownPromptEditor
          v-model="form.llm_system_prompt"
          :disabled="loading || saving"
        />
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
        定时任务由 Web 服务内置的 Python 调度器执行；保存后立即更新，无需操作系统计划任务。
      </p>
    </el-form>
  </div>
</template>

<style scoped>
.config-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.config-title,
.config-note {
  margin-top: 0;
}

.config-title {
  margin-bottom: 0;
}

.config-actions {
  display: flex;
  gap: 8px;
}

.config-form {
  max-width: 1080px;
}

.prompt-form-item :deep(.el-form-item__content) {
  display: block;
}
</style>
