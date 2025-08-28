import axios from 'axios'
import { 
  OrchestrationRequest, 
  OrchestrationResponse, 
  EnhancedOrchestrationRequest,
  EnhancedOrchestrationResponse,
  CapabilitiesResponse,
  MiddlewareStatusResponse,
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

  // M3/M4 Enhanced Query Submission
  async submitEnhancedQuery(request: EnhancedOrchestrationRequest): Promise<EnhancedOrchestrationResponse> {
    const response = await api.post<EnhancedOrchestrationResponse>(API_ENDPOINTS.SUBMIT_QUERY.replace('/api', ''), request)
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

  // M3/M4 Advanced Endpoint Methods
  async getCapabilities(): Promise<CapabilitiesResponse> {
    const response = await api.get<CapabilitiesResponse>(API_ENDPOINTS.CAPABILITIES.replace('/api', ''))
    return response.data
  },

  async getMiddlewareStatus(): Promise<MiddlewareStatusResponse> {
    const response = await api.get<MiddlewareStatusResponse>(API_ENDPOINTS.MIDDLEWARE_STATUS.replace('/api', ''))
    return response.data
  },

  createEventSource(streamUrl: string): EventSource {
    return new EventSource(streamUrl)
  },
}

export default apiService