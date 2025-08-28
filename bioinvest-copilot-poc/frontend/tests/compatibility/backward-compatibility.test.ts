/**
 * Backward Compatibility Tests
 * Ensures M3/M4 enhanced types remain compatible with existing v3.0 code
 */

import { describe, it, expect } from 'vitest'
import { 
  OrchestrationRequest, 
  OrchestrationResponse,
  EnhancedOrchestrationRequest,
  EnhancedOrchestrationResponse,
  apiService 
} from '../../src/services/api'

describe('Backward Compatibility', () => {
  describe('Request Interface Compatibility', () => {
    it('should allow v3.0 requests to be used with enhanced interface', () => {
      // Legacy v3.0 request
      const legacyRequest: OrchestrationRequest = {
        query: "Test backward compatibility",
        sources: ["pubmed", "clinical_trials"],
        options: {
          max_results_per_source: 25,
          include_synthesis: true,
          priority: "balanced"
        }
      }

      // Should be assignable to enhanced interface
      const enhancedRequest: EnhancedOrchestrationRequest = legacyRequest
      
      expect(enhancedRequest.query).toBe("Test backward compatibility")
      expect(enhancedRequest.options.max_results_per_source).toBe(25)
      expect(enhancedRequest.options.priority).toBe("balanced")
      
      // M3/M4 fields should be optional/undefined
      expect(enhancedRequest.options.budget_ms).toBeUndefined()
      expect(enhancedRequest.options.retry_strategy).toBeUndefined()
      expect(enhancedRequest.options.citation_format).toBeUndefined()
    })

    it('should maintain type safety for enhanced requests', () => {
      const enhancedRequest: EnhancedOrchestrationRequest = {
        query: "Advanced M3/M4 features",
        sources: ["pubmed", "rag"],
        options: {
          max_results_per_source: 30,
          include_synthesis: true,
          priority: "comprehensive",
          // M3 options
          budget_ms: 20000,
          enable_partial_results: true,
          retry_strategy: "exponential",
          parallel_execution: true,
          // M4 options
          citation_format: "full",
          quality_threshold: 0.8,
          checkpoint_enabled: true
        }
      }

      expect(enhancedRequest.options.budget_ms).toBe(20000)
      expect(enhancedRequest.options.citation_format).toBe("full")
      expect(enhancedRequest.options.quality_threshold).toBe(0.8)
    })
  })

  describe('API Service Compatibility', () => {
    it('should maintain existing submitQuery method signature', () => {
      expect(typeof apiService.submitQuery).toBe('function')
      expect(apiService.submitQuery.length).toBe(1) // One parameter
    })

    it('should provide new submitEnhancedQuery method', () => {
      expect(typeof apiService.submitEnhancedQuery).toBe('function')
      expect(apiService.submitEnhancedQuery.length).toBe(1) // One parameter
    })

    it('should provide new advanced endpoint methods', () => {
      expect(typeof apiService.getCapabilities).toBe('function')
      expect(typeof apiService.getMiddlewareStatus).toBe('function')
    })
  })
})