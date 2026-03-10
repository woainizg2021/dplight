import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 10000,
})

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

api.interceptors.response.use(
  (response) => {
    return response
  },
  async (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Dashboard API
export const dashboardAPI = {
  getTodayDashboard: async () => {
    const response = await api.get('/dashboard/today')
    return response.data
  }
}

// Fixed APIs to match call sites and return data directly

export const fetchCustomerRanking = async (company_key: string, start_date: string, end_date: string) => {
  const response = await api.get('/sales/customer-rank', { params: { company_key, start_date, end_date } })
  return response.data
}

export const fetchSalesDetails = async (company_key: string, params: any) => {
  const response = await api.get('/sales/details', { params: { company_key, ...params } })
  return response.data
}

export const fetchSkuRanking = async (company_key: string, start_date: string, end_date: string) => {
  const response = await api.get('/sales/sku-rank', { params: { company_key, start_date, end_date } })
  return response.data
}

export const fetchGroupDailySummary = async (date?: string) => {
  const response = await api.get('/dashboard/today', { params: { date } })
  return response.data
}

export const fetchSalesDailyDetails = async (company_key: string, date: string) => {
  const response = await api.get('/sales/daily-details', { params: { company_key, date } })
  return response.data
}

export default api
