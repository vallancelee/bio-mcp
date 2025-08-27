import { useState, useEffect, useCallback } from 'react'
import { StreamEvent, QueryResults } from '@/shared-types'
import { apiService } from '@/services/api'

interface UseStreamingResultsProps {
  streamUrl: string | null
  queryId: string | null
  onComplete?: (results: QueryResults) => void
}

export const useStreamingResults = ({
  streamUrl,
  queryId,
  onComplete,
}: UseStreamingResultsProps) => {
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentStatus, setCurrentStatus] = useState<string>('idle')

  const addEvent = useCallback((event: StreamEvent) => {
    setEvents(prev => [...prev, event])
    setCurrentStatus(event.event)

    // Handle completion events
    if (event.event === 'query_completed' && queryId && onComplete) {
      apiService.getQueryStatus(queryId)
        .then(onComplete)
        .catch(console.error)
    }
  }, [queryId, onComplete])

  useEffect(() => {
    if (!streamUrl) {
      setEvents([])
      setIsConnected(false)
      setError(null)
      setCurrentStatus('idle')
      return
    }

    let eventSource: EventSource | null = null

    try {
      eventSource = apiService.createEventSource(streamUrl)
      
      eventSource.onopen = () => {
        setIsConnected(true)
        setError(null)
      }

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          const streamEvent: StreamEvent = {
            event: 'message', // default event type for onmessage
            timestamp: data.timestamp || new Date().toISOString(),
            data: data,
            query_id: data.query_id
          }
          addEvent(streamEvent)
        } catch (err) {
          console.error('Failed to parse stream event:', err)
        }
      }

      eventSource.onerror = (event) => {
        console.error('EventSource error:', event)
        setError('Connection to stream lost')
        setIsConnected(false)
        
        // Auto-reconnect logic
        if (eventSource?.readyState === EventSource.CLOSED) {
          setTimeout(() => {
            setError(null)
          }, 3000)
        }
      }

      // Handle specific event types
      eventSource.addEventListener('source_started', (event) => {
        const data = JSON.parse((event as MessageEvent).data)
        const streamEvent: StreamEvent = {
          event: 'source_started',
          timestamp: data.timestamp || new Date().toISOString(),
          data: data,
          query_id: data.query_id,
          source: data.source
        }
        addEvent(streamEvent)
      })

      eventSource.addEventListener('source_completed', (event) => {
        const data = JSON.parse((event as MessageEvent).data)
        const streamEvent: StreamEvent = {
          event: 'source_completed',
          timestamp: data.timestamp || new Date().toISOString(),
          data: data,
          query_id: data.query_id,
          source: data.source
        }
        addEvent(streamEvent)
      })

      eventSource.addEventListener('synthesis_started', (event) => {
        const data = JSON.parse((event as MessageEvent).data)
        const streamEvent: StreamEvent = {
          event: 'synthesis_started',
          timestamp: data.timestamp || new Date().toISOString(),
          data: data,
          query_id: data.query_id
        }
        addEvent(streamEvent)
      })

      eventSource.addEventListener('synthesis_completed', (event) => {
        const data = JSON.parse((event as MessageEvent).data)
        const streamEvent: StreamEvent = {
          event: 'synthesis_completed',
          timestamp: data.timestamp || new Date().toISOString(),
          data: data,
          query_id: data.query_id
        }
        addEvent(streamEvent)
      })

      eventSource.addEventListener('query_completed', (event) => {
        const data = JSON.parse((event as MessageEvent).data)
        const streamEvent: StreamEvent = {
          event: 'query_completed',
          timestamp: data.timestamp || new Date().toISOString(),
          data: data,
          query_id: data.query_id
        }
        addEvent(streamEvent)
        setIsConnected(false)
      })

      eventSource.addEventListener('query_failed', (event) => {
        const data = JSON.parse((event as MessageEvent).data)
        const streamEvent: StreamEvent = {
          event: 'query_failed',
          timestamp: data.timestamp || new Date().toISOString(),
          data: data,
          query_id: data.query_id
        }
        addEvent(streamEvent)
        setError('Query failed')
        setIsConnected(false)
      })

    } catch (err) {
      setError('Failed to connect to stream')
      setIsConnected(false)
    }

    return () => {
      if (eventSource) {
        eventSource.close()
        setIsConnected(false)
      }
    }
  }, [streamUrl, addEvent])

  const reset = useCallback(() => {
    setEvents([])
    setError(null)
    setCurrentStatus('idle')
  }, [])

  return {
    events,
    isConnected,
    error,
    currentStatus,
    reset,
  }
}