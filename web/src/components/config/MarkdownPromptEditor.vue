<script setup lang="ts">
import { computed, nextTick, useTemplateRef } from "vue";

defineProps<{
  disabled?: boolean;
}>();

const model = defineModel<string>({ required: true });
const editor = useTemplateRef<HTMLTextAreaElement>("editor");
const characterCount = computed(() => model.value.length);

interface SelectionReplacement {
  text: string;
  selectionStart: number;
  selectionEnd: number;
}

async function replaceSelection(
  formatter: (selection: string) => SelectionReplacement,
) {
  const textarea = editor.value;
  if (!textarea) return;

  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const replacement = formatter(model.value.slice(start, end));
  model.value =
    model.value.slice(0, start) +
    replacement.text +
    model.value.slice(end);

  await nextTick();
  textarea.focus();
  textarea.setSelectionRange(
    start + replacement.selectionStart,
    start + replacement.selectionEnd,
  );
}

function insertHeading() {
  void replaceSelection((selection) => {
    const content = selection || "标题";
    const text = `## ${content}`;
    return {
      text,
      selectionStart: 3,
      selectionEnd: text.length,
    };
  });
}

function insertBold() {
  void replaceSelection((selection) => {
    const content = selection || "重点内容";
    const text = `**${content}**`;
    return {
      text,
      selectionStart: 2,
      selectionEnd: text.length - 2,
    };
  });
}

function insertList(ordered: boolean) {
  void replaceSelection((selection) => {
    const lines = (selection || "列表项").split("\n");
    const text = lines
      .map((line, index) => `${ordered ? `${index + 1}.` : "-"} ${line}`)
      .join("\n");
    return {
      text,
      selectionStart: 0,
      selectionEnd: text.length,
    };
  });
}

function insertCodeBlock() {
  void replaceSelection((selection) => {
    const content = selection || "示例内容";
    const text = `\`\`\`text\n${content}\n\`\`\``;
    return {
      text,
      selectionStart: 8,
      selectionEnd: 8 + content.length,
    };
  });
}

function insertIndent() {
  void replaceSelection((selection) => {
    const text = `  ${selection}`;
    return {
      text,
      selectionStart: 2,
      selectionEnd: text.length,
    };
  });
}
</script>

<template>
  <div class="markdown-editor">
    <div class="markdown-toolbar" aria-label="Markdown 编辑工具栏">
      <el-button size="small" :disabled="disabled" @click="insertHeading">
        标题
      </el-button>
      <el-button size="small" :disabled="disabled" @click="insertBold">
        加粗
      </el-button>
      <el-button size="small" :disabled="disabled" @click="insertList(false)">
        无序列表
      </el-button>
      <el-button size="small" :disabled="disabled" @click="insertList(true)">
        有序列表
      </el-button>
      <el-button size="small" :disabled="disabled" @click="insertCodeBlock">
        代码块
      </el-button>
    </div>

    <textarea
      ref="editor"
      v-model="model"
      class="markdown-textarea"
      :disabled="disabled"
      spellcheck="false"
      aria-label="周报提示词 Markdown 编辑器"
      @keydown.tab.prevent="insertIndent"
    />

    <div class="markdown-footer">
      <span>支持 Markdown 标题、列表、加粗和代码块；GitLab 提交记录会自动附加。</span>
      <span>{{ characterCount }} 字符</span>
    </div>
  </div>
</template>

<style scoped>
.markdown-editor {
  width: 100%;
  border: 1px solid var(--el-border-color);
  border-radius: var(--el-border-radius-base);
  overflow: hidden;
}

.markdown-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color);
}

.markdown-toolbar :deep(.el-button + .el-button) {
  margin-left: 0;
}

.markdown-textarea {
  display: block;
  box-sizing: border-box;
  width: 100%;
  min-height: 520px;
  padding: 14px 16px;
  border: 0;
  outline: none;
  resize: vertical;
  color: var(--el-text-color-primary);
  background: var(--el-bg-color);
  font: 14px/1.65 "Cascadia Code", Consolas, monospace;
}

.markdown-textarea:focus {
  box-shadow: inset 0 0 0 1px var(--el-color-primary);
}

.markdown-textarea:disabled {
  cursor: not-allowed;
  color: var(--el-text-color-placeholder);
  background: var(--el-disabled-bg-color);
}

.markdown-footer {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 7px 10px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-lighter);
  border-top: 1px solid var(--el-border-color);
  font-size: 12px;
}
</style>
