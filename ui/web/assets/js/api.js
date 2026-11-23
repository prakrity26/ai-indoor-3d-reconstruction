// Thin client for the FastAPI backend. Every call returns parsed JSON or throws ApiError.

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function request(method, url, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    throw new ApiError(0, "The server is not reachable. Is the API running?");
  }
  if (response.status === 204) return null;
  const text = await response.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = null; }
  if (!response.ok) {
    const detail = data && (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
    throw new ApiError(response.status, detail || `Request failed (${response.status}).`);
  }
  return data;
}

export const api = {
  config: () => request("GET", "/api/config"),
  health: () => request("GET", "/health"),
  list: async () => (await request("GET", "/jobs")).jobs || [],
  get: (id) => request("GET", `/jobs/${encodeURIComponent(id)}`),
  update: (id, fields) => request("PATCH", `/jobs/${encodeURIComponent(id)}`, fields),
  remove: (id) => request("DELETE", `/jobs/${encodeURIComponent(id)}`),
  retry: (id) => request("POST", `/jobs/${encodeURIComponent(id)}/retry`),
  setVisibility: (id, visibility) => request("PUT", `/jobs/${encodeURIComponent(id)}/visibility`, { visibility }),
  rotateShare: (id) => request("POST", `/jobs/${encodeURIComponent(id)}/share/rotate`),
  studio: (id) => request("GET", `/jobs/${encodeURIComponent(id)}/studio.json`),
  saveStudio: (id, doc) => request("PUT", `/jobs/${encodeURIComponent(id)}/studio.json`, doc),
  shared: (token) => request("GET", `/shared/${encodeURIComponent(token)}`),

  /** Upload with progress. onProgress(fraction 0..1). Resolves to the created project. */
  upload(file, { name, description }, onProgress) {
    return new Promise((resolve, reject) => {
      const form = new FormData();
      form.append("file", file, file.name);
      form.append("name", name || "");
      form.append("description", description || "");
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/jobs");
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) onProgress(event.loaded / event.total);
      };
      xhr.onerror = () => reject(new ApiError(0, "Upload failed: the server is not reachable."));
      xhr.onload = () => {
        let data = null;
        try { data = JSON.parse(xhr.responseText); } catch { data = null; }
        if (xhr.status >= 200 && xhr.status < 300) resolve(data);
        else reject(new ApiError(xhr.status, (data && data.detail) || `Upload failed (${xhr.status}).`));
      };
      xhr.send(form);
    });
  },
};
