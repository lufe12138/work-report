import { createRouter, createWebHistory } from "vue-router";
import AdminLayout from "../layouts/AdminLayout.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      component: AdminLayout,
      children: [
        { path: "", name: "dashboard", component: () => import("../views/Dashboard.vue") },
        { path: "runs", name: "runs", component: () => import("../views/RunList.vue") },
        {
          path: "runs/:id",
          name: "run-detail",
          component: () => import("../views/RunDetail.vue"),
          props: true,
        },
        { path: "config", name: "config", component: () => import("../views/Config.vue") },
        {
          path: "holidays",
          name: "holidays",
          component: () => import("../views/Holidays.vue"),
        },
        {
          path: "project-names",
          name: "project-names",
          component: () => import("../views/ProjectNames.vue"),
        },
      ],
    },
  ],
});

export default router;
