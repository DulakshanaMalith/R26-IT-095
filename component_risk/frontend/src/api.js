const API = "/api";

async function request(path, options = {}, fallback = "Request failed.") {
  let response;
  try {
    response = await fetch(`${API}${path}`, { credentials: "include", ...options });
  } catch {
    throw new Error("Backend is unavailable. Start the FastAPI server on port 8000.");
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    throw new Error(payload?.error || payload?.detail || fallback);
  }

  return payload;
}

const jsonPost = (body) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body)
});

export const getMe = () => request("/me");
export const login = (email, password) =>
  request("/login", jsonPost({ email, password }), "Invalid email or password.");
export const registerAccount = (data) =>
  request("/register", jsonPost(data), "Registration failed.");
export const logout = () => request("/logout", { method: "POST" });
export const getProjects = () => request("/projects");
export const getProject = (id) => request(`/projects/${id}`);
export const getAnalytics = (id, force = false) =>
  request(`/dashboard-data?project_id=${id}${force ? "&force=1" : ""}`,
    {}, "Could not load analytics.");

export const createProject = (data) =>
  request("/projects", jsonPost(data), "Could not create the project.");

export const uploadTeams = (file) => {
  const body = new FormData();
  body.append("file", file);
  return request("/projects/upload", { method: "POST", body }, "Upload failed.");
};

export const TEMPLATE_URL = "/api/team-template";
