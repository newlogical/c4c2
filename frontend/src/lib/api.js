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
  zone: (payload) => http.post("/audio/zone", payload).then((r) => r.data),
  audioGroup: (source_id, volume) =>
    http.post("/audio/group", { source_id, volume }).then((r) => r.data),
  climate: (payload) => http.post("/climate", payload).then((r) => r.data),
  cameraSnapshot: () => http.post("/camera/snapshot").then((r) => r.data),
  scene: (scene_id) => http.post(`/scene/${scene_id}`).then((r) => r.data),
};

export default api;
