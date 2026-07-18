import axios from "axios"

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const message = err?.response?.data?.detail || err?.message || "Request failed"
    return Promise.reject(new Error(message))
  },
)
