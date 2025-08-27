import axios from 'axios'
import { 
  OrchestrationRequest, 
  OrchestrationResponse, 
  QueryResults, 
  ActiveQueriesResponse,
  ActiveQuery,
  API_ENDPOINTS 
} from '@/shared-types'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export const apiService = {
  async submitQuery(request: OrchestrationRequest): Promise<OrchestrationResponse> {
    const response = await api.post<OrchestrationResponse>(API_ENDPOINTS.SUBMIT_QUERY.replace('/api', ''), request)
    return response.data
  },

  async getQueryStatus(queryId: string): Promise<QueryResults> {
    const response = await api.get<QueryResults>(`${API_ENDPOINTS.QUERY_STATUS.replace('/api', '')}/${queryId}`)
    return response.data
  },

  async getActiveQueries(): Promise<ActiveQuery[]> {
    const response = await api.get<ActiveQueriesResponse>(API_ENDPOINTS.ACTIVE_QUERIES.replace('/api', ''))
    return response.data.active_queries
  },

  createEventSource(streamUrl: string): EventSource {
    return new EventSource(streamUrl)
  },
}

export default apiService