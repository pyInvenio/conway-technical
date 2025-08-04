// src/routes/api/incidents/[id]/+server.ts
import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export const GET: RequestHandler = async ({ params, cookies }) => {
    const { id } = params;
    
    // Check authentication
    const sessionId = cookies.get('session');
    
    if (!sessionId) {
        return json({ message: 'Unauthorized' }, { status: 401 });
    }
    
    try {
        // Fetch detailed anomaly data from backend
        const response = await fetch(`${BACKEND_URL}/api/v1/anomalies/${id}`, {
            headers: {
                'Authorization': `Bearer ${sessionId}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            if (response.status === 404) {
                return json({ message: 'Incident not found' }, { status: 404 });
            }
            throw new Error(`Failed to fetch incident: ${response.status}`);
        }
        
        const anomaly = await response.json();
        
        // Transform to include both old and new format for compatibility
        const detailedIncident = {
            ...transformAnomalyToIncident(anomaly),
            
            // Additional detailed data for incident modal
            detailed_analysis: {
                // Behavioral Analysis Details
                behavioral_features: anomaly.behavioral_analysis?.behavioral_features || [],
                anomalous_features: anomaly.behavioral_analysis?.anomalous_features || [],
                baseline_comparison: anomaly.behavioral_analysis?.baseline_comparison || null,
                
                // Content Analysis Details
                secret_detections: anomaly.content_analysis?.secret_detections || [],
                suspicious_files: anomaly.content_analysis?.file_analysis?.suspicious_files || [],
                high_risk_indicators: anomaly.content_analysis?.high_risk_indicators || [],
                
                // Temporal Analysis Details
                temporal_patterns: anomaly.temporal_analysis?.detected_patterns || [],
                burst_analysis: extractBurstAnalysis(anomaly.temporal_analysis),
                coordination_analysis: extractCoordinationAnalysis(anomaly.temporal_analysis),
                
                // Repository Context
                repository_info: anomaly.repository_context?.repository_info || {},
                contributor_analysis: anomaly.repository_context?.contributor_analysis || {},
                context_insights: anomaly.repository_context?.context_insights || [],
                
                // AI Summary and Recommendations
                ai_summary: anomaly.ai_summary,
                recommendations: generateRecommendations(anomaly),
                
                // Processing metadata
                processing_timestamp: anomaly.processing_timestamp,
                detection_weights: anomaly.detection_weights
            }
        };
        
        return json(detailedIncident);
        
    } catch (error) {
        console.error('Detailed incident fetch error:', error);
        return json({ message: 'Failed to fetch incident details' }, { status: 500 });
    }
};

// Reuse the transformation function from the main incidents endpoint
function transformAnomalyToIncident(anomaly: any) {
    return {
        id: anomaly.event_id,
        repo_name: anomaly.repository_name,
        user_login: anomaly.user_login,
        event_type: anomaly.event_type,
        created_at: anomaly.timestamp,
        
        severity: anomaly.final_anomaly_score,
        severity_level: anomaly.severity_level,
        title: generateIncidentTitle(anomaly),
        incident_type: determineIncidentType(anomaly),
        root_cause: generateRootCause(anomaly),
        entropy_score: anomaly.detection_scores?.behavioral || 0,
        
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
    if (anomaly.content_analysis?.secret_detections?.length > 0) {
        return 'secret_exposure';
    }
    
    if (anomaly.temporal_analysis?.detected_patterns?.length > 0) {
        const pattern = anomaly.temporal_analysis.detected_patterns[0];
        return pattern.type;
    }
    
    if (anomaly.behavioral_analysis?.anomalous_features?.length > 0) {
        return 'behavioral_anomaly';
    }
    
    return 'general_anomaly';
}

function generateRootCause(anomaly: any): string[] {
    const causes: string[] = [];
    
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
    
    if (anomaly.ai_summary) {
        causes.push(`AI Analysis: ${anomaly.ai_summary}`);
    }
    
    if (causes.length === 0) {
        causes.push(`Anomaly score: ${(anomaly.final_anomaly_score * 100).toFixed(1)}% - Multiple factors contributed to this detection`);
    }
    
    return causes.slice(0, 5);
}

function extractBurstAnalysis(temporalAnalysis: any) {
    if (!temporalAnalysis?.detected_patterns) return null;
    
    const burstPattern = temporalAnalysis.detected_patterns.find(
        (p: any) => p.type === 'activity_burst'
    );
    
    if (!burstPattern) return null;
    
    return {
        events_per_minute: burstPattern.events_per_minute,
        duration_minutes: burstPattern.duration_minutes,
        event_count: burstPattern.event_count,
        severity: burstPattern.severity,
        start_time: burstPattern.start_time
    };
}

function extractCoordinationAnalysis(temporalAnalysis: any) {
    if (!temporalAnalysis?.detected_patterns) return null;
    
    const coordPattern = temporalAnalysis.detected_patterns.find(
        (p: any) => p.type === 'coordinated_activity'
    );
    
    if (!coordPattern) return null;
    
    return {
        actor_count: coordPattern.actor_count,
        actors: coordPattern.actors || [],
        event_count: coordPattern.event_count,
        duration_minutes: coordPattern.duration_minutes,
        severity: coordPattern.severity
    };
}

function generateRecommendations(anomaly: any): string[] {
    const recommendations: string[] = [];
    
    // Content-based recommendations
    if (anomaly.content_analysis?.secret_detections?.length > 0) {
        recommendations.push('Immediately rotate any exposed credentials');
        recommendations.push('Review and update secret management practices');
        recommendations.push('Consider implementing pre-commit hooks to prevent future exposures');
    }
    
    // Temporal pattern recommendations
    if (anomaly.temporal_analysis?.detected_patterns?.length > 0) {
        const hasCoordination = anomaly.temporal_analysis.detected_patterns.some(
            (p: any) => p.type === 'coordinated_activity'
        );
        const hasBurst = anomaly.temporal_analysis.detected_patterns.some(
            (p: any) => p.type === 'activity_burst'
        );
        
        if (hasCoordination) {
            recommendations.push('Investigate potential coordinated attack or compromised accounts');
            recommendations.push('Review access logs for all involved users');
        }
        
        if (hasBurst) {
            recommendations.push('Verify if the activity burst was legitimate or automated');
            recommendations.push('Consider implementing rate limiting if appropriate');
        }
    }
    
    // Behavioral recommendations
    if (anomaly.behavioral_analysis?.anomalous_features?.length > 0) {
        recommendations.push('Review user access patterns and permissions');
        recommendations.push('Consider additional monitoring for this user account');
    }
    
    // Repository-specific recommendations
    const repoCriticality = anomaly.repository_context?.repository_criticality_score || 0;
    if (repoCriticality > 0.7) {
        recommendations.push('High-value repository: escalate to security team immediately');
        recommendations.push('Consider temporary access restrictions while investigating');
    }
    
    // General recommendations
    recommendations.push('Document incident for future reference');
    recommendations.push('Update detection rules based on findings');
    
    return recommendations.slice(0, 8); // Limit to top 8 recommendations
}