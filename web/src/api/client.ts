import axios from "axios";
import { ElMessage } from "element-plus";

const client = axios.create({
  baseURL: "/api",
  timeout: 60000,
});

client.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const detail =
      error?.response?.data?.detail ||
      error?.message ||
      "请求失败";
    const msg = typeof detail === "string" ? detail : JSON.stringify(detail);
    ElMessage.error(msg);
    return Promise.reject(error);
  }
);

export default client;

export async function getDashboard() {
  const { data } = await client.get("/dashboard");
  return data;
}

export async function getConfig() {
  const { data } = await client.get("/config");
  return data;
}

export async function updateConfig(payload: Record<string, unknown>) {
  const { data } = await client.put("/config", payload);
  return data;
}

export async function testDingtalk() {
  const { data } = await client.post("/config/test-dingtalk");
  return data;
}

export async function testLlm() {
  const { data } = await client.post("/config/test-llm", null, { timeout: 120000 });
  return data as {
    ok: boolean;
    message: string;
    prompt: string;
    reply: string;
    model: string;
    base_url: string;
  };
}

export async function getProjectNames() {
  const { data } = await client.get("/project-names");
  return data;
}

export async function saveProjectNames(items: { project_key: string; display_name: string }[]) {
  const { data } = await client.put("/project-names", { items });
  return data;
}

export async function addProjectName(item: { project_key: string; display_name: string }) {
  const { data } = await client.post("/project-names", item);
  return data;
}

export async function deleteProjectName(key: string) {
  const { data } = await client.delete(`/project-names/${encodeURIComponent(key)}`);
  return data;
}

export async function listRuns(params: { page?: number; size?: number; status?: string } = {}) {
  const { data } = await client.get("/runs", { params });
  return data;
}

export async function getRun(id: number | string) {
  const { data } = await client.get(`/runs/${id}`);
  return data;
}

export async function createRun(body: {
  skip_llm?: boolean;
  send_dingtalk?: boolean;
  if_last_workday?: boolean;
}) {
  const { data } = await client.post("/runs", body);
  return data;
}

export async function getHoliday() {
  const { data } = await client.get("/system/holiday");
  return data;
}

export interface HolidayItem {
  date: string;
  description: string;
  is_makeup: boolean;
}

interface HolidayListResponse {
  items: HolidayItem[];
}

export async function getHolidays(): Promise<HolidayListResponse> {
  const { data } = await client.get("/holidays");
  return data as HolidayListResponse;
}

export async function saveHolidays(items: HolidayItem[]): Promise<HolidayListResponse> {
  const { data } = await client.put("/holidays", { items });
  return data as HolidayListResponse;
}

export async function deleteHoliday(date: string) {
  const { data } = await client.delete(`/holidays/${encodeURIComponent(date)}`);
  return data;
}
