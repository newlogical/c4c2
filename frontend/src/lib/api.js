import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const http = axios.create({ baseURL: API });

export const api = {
  getState: () => http.get("/state").then((r) => r.data),
  verifyPin: (pin) => http.post("/auth/pin", { pin }).then((r) => r.data),
  reset: () => http.post("/state/reset").then((r) => r.data),
  route: (display_id, source_id) =>
    http.post("/matrix/route", { display_id, source_id }).then((r) => r.data),
  broadcast: (source_id) =>
    http.post("/matrix/broadcast", { source_id }).then((r) => r.data),
  displayPower: (display_id, power) =>
    http.post("/display/power", { display_id, power }).then((r) => r.data),
  remote: (source_id, key) =>
    http.post("/display/remote", { source_id, key }).then((r) => r.data),
  tvKey: (display_id, key) =>
    http.post("/display/tvkey", { source_id: display_id, key }).then((r) => r.data),
  tvVolume: (display_id, volume) =>
    http.post("/display/tvvolume", { display_id, volume }).then((r) => r.data),
  zone: (payload) => http.post("/audio/zone", payload).then((r) => r.data),
  audioGroup: (source_id, volume) =>
    http.post("/audio/group", { source_id, volume }).then((r) => r.data),
  climate: (payload) => http.post("/climate", payload).then((r) => r.data),
  cameraSnapshot: () => http.post("/camera/snapshot").then((r) => r.data),
  scene: (scene_id) => http.post(`/scene/${scene_id}`).then((r) => r.data),
  // Camera streaming
  cameraStream: () => http.get("/camera/stream").then((r) => r.data),
  // Device config
  updateConfig: (config) => http.put("/config", { config }).then((r) => r.data),
  testConnection: (device) => http.post(`/config/test/${device}`).then((r) => r.data),
  // Automations
  getAutomations: () => http.get("/automations").then((r) => r.data),
  createAutomation: (payload) => http.post("/automations", payload).then((r) => r.data),
  updateAutomation: (id, payload) => http.put(`/automations/${id}`, payload).then((r) => r.data),
  deleteAutomation: (id) => http.delete(`/automations/${id}`).then((r) => r.data),
  runAutomation: (id) => http.post(`/automations/${id}/run`).then((r) => r.data),
  triggerEvent: (event) => http.post(`/trigger/${event}`).then((r) => r.data),
};

export const BACKEND = process.env.REACT_APP_BACKEND_URL;

export default api;
