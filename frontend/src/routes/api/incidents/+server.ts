// src/routes/api/incidents/+server.ts
import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

// Your backend URL
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export const GET: RequestHandler = async ({ url, cookies }) => {
    // Check authentication
    const sessionId = cookies.get('session');
    
    if (!sessionId) {
        return json({ message: 'Unauthorized' }, { status: 401 });
    }
    
    try {
        // Get query parameters for pagination and filtering
        const page = url.searchParams.get('page') || '1';
        const limit = url.searchParams.get('limit') || '20';
        const severity = url.searchParams.get('severity');
        const user = url.searchParams.get('user');
        const repo = url.searchParams.get('repo');
        const since = url.searchParams.get('since');
        
        // Build query parameters
        const params = new URLSearchParams({
            page,
            limit
        });
        
        if (severity) params.append('severity', severity);
        if (user) params.append('user', user);
        if (repo) params.append('repo', repo);
        if (since) params.append('since', since);
        
        // Fetch from your Python backend - updated endpoint for new anomaly system
        const response = await fetch(`${BACKEND_URL}/api/v1/anomalies?${params}`, {
            headers: {
                'Authorization': `Bearer ${sessionId}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error(`Failed to fetch anomalies: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Transform the new anomaly data to match existing frontend expectations
        const transformedData = {
            incidents: data.anomalies?.map(transformAnomalyToIncident) || [],
            pagination: data.pagination || {
                page: parseInt(page),
                limit: parseInt(limit),
                total: 0,
                pages: 0,
                has_next: false,
                has_prev: false
            },
            stats: data.stats || {}
        };
        
        return json(transformedData);
        
    } catch (error) {
        console.error('Anomalies fetch error:', error);
        return json({ message: 'Failed to fetch anomalies' }, { status: 500 });
    }
};

// Transform new anomaly detection format to existing incident format
function transformAnomalyToIncident(anomaly: any) {
    return {
        id: anomaly.event_id,
        repo_name: anomaly.repository_name,
        user_login: anomaly.user_login,
        event_type: anomaly.event_type,
        created_at: anomaly.timestamp,
        
        // Map new severity system to old format
        severity: anomaly.final_anomaly_score,
        severity_level: anomaly.severity_level,
        title: generateIncidentTitle(anomaly),
        
        // Map new detection categories to old incident_type
        incident_type: determineIncidentType(anomaly),
        
        // Generate root cause from detection analysis
        root_cause: generateRootCause(anomaly),
        
        // Map entropy-like metrics
        entropy_score: anomaly.detection_scores?.behavioral || 0,
        
        // Include new anomaly-specific data for enhanced UI
        anomaly_data: {
            detection_scores: anomaly.detection_scores,
            behavioral_analysis: anomaly.behavioral_analysis,
            content_analysis: anomaly.content_analysis,
            temporal_analysis: anomaly.temporal_analysis,
            repository_context: anomaly.repository_context,
            ai_summary: anomaly.ai_summary,
            processing_timestamp: anomaly.processing_timestamp
        }
    };
}

function generateIncidentTitle(anomaly: any): string {
    const severityLevel = anomaly.severity_level;
    const eventType = anomaly.event_type;
    const repo = anomaly.repository_name;
    
    // Generate titles based on detection type
    if (anomaly.content_analysis?.secret_detections?.length > 0) {
        const secretCount = anomaly.content_analysis.secret_detections.length;
        return `${severityLevel} Security Alert: ${secretCount} secret(s) detected in ${repo}`;
    }
    
    if (anomaly.temporal_analysis?.detected_patterns?.length > 0) {
        const pattern = anomaly.temporal_analysis.detected_patterns[0];
        return `${severityLevel} Activity Alert: ${pattern.type.replace(/_/g, ' ')} in ${repo}`;
    }
    
    if (anomaly.behavioral_analysis?.anomalous_features?.length > 0) {
        return `${severityLevel} Behavior Alert: Unusual ${eventType} activity in ${repo}`;
    }
    
    return `${severityLevel} Anomaly: Suspicious ${eventType} activity in ${repo}`;
}

function determineIncidentType(anomaly: any): string {
    // Prioritize by severity and type of detection
    if (anomaly.content_analysis?.secret_detections?.length > 0) {
        return 'secret_exposure';
    }
    
    if (anomaly.temporal_analysis?.detected_patterns?.length > 0) {
        const pattern = anomaly.temporal_analysis.detected_patterns[0];
        return pattern.type; // activity_burst, coordinated_activity, etc.
    }
    
    if (anomaly.behavioral_analysis?.anomalous_features?.length > 0) {
        return 'behavioral_anomaly';
    }
    
    return 'general_anomaly';
}

function generateRootCause(anomaly: any): string[] {
    const causes: string[] = [];
    
    // Add causes based on detection results
    if (anomaly.content_analysis?.secret_detections?.length > 0) {
        anomaly.content_analysis.secret_detections.forEach((secret: any) => {
            causes.push(`${secret.pattern_description} detected in ${secret.location}`);
        });
    }
    
    if (anomaly.temporal_analysis?.detected_patterns?.length > 0) {
        anomaly.temporal_analysis.detected_patterns.forEach((pattern: any) => {
            causes.push(`${pattern.type.replace(/_/g, ' ')} detected: ${pattern.event_count} events in ${pattern.duration_minutes || 'short'} timeframe`);
        });
    }
    
    if (anomaly.behavioral_analysis?.anomalous_features?.length > 0) {
        anomaly.behavioral_analysis.anomalous_features.forEach((feature: any) => {
            causes.push(`Unusual ${feature.feature_name.replace(/_/g, ' ')}: ${feature.deviation_description || 'significant deviation from baseline'}`);
        });
    }
    
    // Add AI summary as additional context if available
    if (anomaly.ai_summary) {
        causes.push(`AI Analysis: ${anomaly.ai_summary}`);
    }
    
    // Fallback if no specific causes identified
    if (causes.length === 0) {
        causes.push(`Anomaly score: ${(anomaly.final_anomaly_score * 100).toFixed(1)}% - Multiple factors contributed to this detection`);
    }
    
    return causes.slice(0, 5); // Limit to top 5 causes
}