export interface PatternInsight {
  category: 'behavioral' | 'content' | 'temporal' | 'repository';
  severity: 'high' | 'medium' | 'low';
  title: string;
  description: string;
  technical_detail?: string;
  recommendation?: string;
}

export interface AnalysisBreakdown {
  primary_reasons: PatternInsight[];
  supporting_factors: PatternInsight[];
  risk_assessment: string;
  confidence: number;
}

export function interpretBehavioralPatterns(analysis: any): PatternInsight[] {
  const insights: PatternInsight[] = [];
  
  if (!analysis || !analysis.detected_anomalies) return insights;

  for (const anomaly of analysis.detected_anomalies) {
    const insight = interpretBehavioralAnomaly(anomaly);
    if (insight) insights.push(insight);
  }

  return insights;
}

function interpretBehavioralAnomaly(anomaly: any): PatternInsight | null {
  const { type, feature_name, current_value, threshold, severity } = anomaly;
  
  
  switch (type) {
    case 'high_activity_heuristic':
      return interpretHighActivityPattern(feature_name, current_value, threshold, severity);
    
    case 'low_diversity_pattern':
      return interpretLowDiversityPattern(feature_name, current_value, threshold, severity);
    
    case 'burst_activity_pattern':
      return interpretBurstPattern(feature_name, current_value, threshold, severity);
    
    default:
      return {
        category: 'behavioral',
        severity: severity > 0.8 ? 'high' : severity > 0.5 ? 'medium' : 'low',
        title: `Unusual ${feature_name.replace(/_/g, ' ')}`,
        description: `Detected abnormal pattern in ${feature_name.replace(/_/g, ' ')}`,
        technical_detail: `Current: ${current_value}`
      };
  }
}

function interpretHighActivityPattern(feature: string, value: number, threshold: number, severity: number): PatternInsight {
  switch (feature) {
    case 'time_spread_hours':
      return {
        category: 'behavioral',
        severity: severity > 0.8 ? 'high' : 'medium',
        title: 'Compressed Time Window',
        description: `All activity occurred within ${value} hour${value !== 1 ? 's' : ''}, which is unusually concentrated`,
        technical_detail: `Activity compressed to ${value}h (normal: >${threshold}h)`,
        recommendation: 'Review if this time compression indicates automated activity or coordinated actions'
      };
    
    case 'off_hours_activity_ratio':
      const percentage = Math.round(value * 100);
      return {
        category: 'behavioral',
        severity: severity > 0.8 ? 'high' : 'medium',
        title: 'Off-Hours Activity',
        description: `${percentage}% of activity occurred outside normal business hours`,
        technical_detail: `Off-hours ratio: ${value} (threshold: ${threshold})`,
        recommendation: 'Verify if off-hours activity aligns with user\'s expected timezone and work patterns'
      };
    
    case 'events_per_hour':
      return {
        category: 'behavioral',
        severity: severity > 0.8 ? 'high' : 'medium',
        title: 'High Event Frequency',
        description: `${value} events per hour, significantly above normal activity levels`,
        technical_detail: `Event rate: ${value}/hour (threshold: ${threshold})`,
        recommendation: 'Check if this represents legitimate bulk operations or potential automation'
      };
    
    default:
      return {
        category: 'behavioral',
        severity: severity > 0.8 ? 'high' : 'medium',
        title: `High ${feature.replace(/_/g, ' ')}`,
        description: `Elevated ${feature.replace(/_/g, ' ')} detected`,
        technical_detail: `Value: ${value} (threshold: ${threshold})`
      };
  }
}

function interpretLowDiversityPattern(feature: string, value: number, threshold: number, severity: number): PatternInsight {
  switch (feature) {
    case 'event_type_entropy':
      return {
        category: 'behavioral',
        severity: 'high',
        title: 'Single Event Type Pattern',
        description: 'All detected events are of the same type, indicating highly focused activity',
        technical_detail: `Event diversity: ${value.toExponential(2)} (threshold: ${threshold})`,
        recommendation: 'Investigate whether this single-purpose activity pattern is expected for this user'
      };
    
    case 'repository_diversity_ratio':
      return {
        category: 'behavioral',
        severity: severity > 0.8 ? 'high' : 'medium',
        title: 'Single Repository Focus',
        description: 'Activity concentrated on a single repository',
        technical_detail: `Repository diversity: ${value} (threshold: ${threshold})`,
        recommendation: 'Verify if concentrated repository activity aligns with user\'s current project assignments'
      };
    
    default:
      return {
        category: 'behavioral',
        severity: severity > 0.8 ? 'high' : 'medium',
        title: `Low ${feature.replace(/_/g, ' ')}`,
        description: `Reduced diversity in ${feature.replace(/_/g, ' ')}`,
        technical_detail: `Value: ${value} (threshold: ${threshold})`
      };
  }
}

function interpretBurstPattern(feature: string, value: number, threshold: number, severity: number): PatternInsight {
  return {
    category: 'behavioral',
    severity: severity > 0.8 ? 'high' : 'medium',
    title: 'Activity Burst Detected',
    description: 'Rapid sequence of events detected in short time frame',
    technical_detail: `Burst intensity: ${value} (threshold: ${threshold})`,
    recommendation: 'Review if burst activity represents legitimate batch operations'
  };
}

export function interpretContentPatterns(analysis: any): PatternInsight[] {
  const insights: PatternInsight[] = [];
  
  if (!analysis) return insights;

  // Check for secret detections
  if (analysis.secret_detections && analysis.secret_detections.length > 0) {
    insights.push({
      category: 'content',
      severity: 'high',
      title: 'Potential Secrets Detected',
      description: `${analysis.secret_detections.length} potential secret(s) found in code or files`,
      recommendation: 'Review detected patterns and ensure no credentials are exposed'
    });
  }

  // Check file analysis
  const fileAnalysis = analysis.file_analysis;
  if (fileAnalysis) {
    if (fileAnalysis.mass_deletions && fileAnalysis.mass_deletions.length > 0) {
      insights.push({
        category: 'content',
        severity: 'high',
        title: 'Mass File Deletions',
        description: `${fileAnalysis.mass_deletions.length} files deleted in bulk operation`,
        recommendation: 'Verify deletions are intentional and consider backup recovery options'
      });
    }

    if (fileAnalysis.large_changes && fileAnalysis.large_changes.length > 0) {
      insights.push({
        category: 'content',
        severity: 'medium',
        title: 'Large File Changes',
        description: `${fileAnalysis.large_changes.length} files with significant modifications`,
        recommendation: 'Review large changes for potential data exfiltration or code injection'
      });
    }

    if (fileAnalysis.binary_changes && fileAnalysis.binary_changes.length > 0) {
      insights.push({
        category: 'content',
        severity: 'medium',
        title: 'Binary File Changes',
        description: `${fileAnalysis.binary_changes.length} binary files modified`,
        recommendation: 'Scan binary files for malware and verify authenticity'
      });
    }

    if (fileAnalysis.credential_modifications && fileAnalysis.credential_modifications.length > 0) {
      insights.push({
        category: 'content',
        severity: 'high',
        title: 'Credential File Changes',
        description: `${fileAnalysis.credential_modifications.length} credential-related files modified`,
        recommendation: 'Immediately review credential changes and rotate affected secrets'
      });
    }
  }

  // High risk indicators
  if (analysis.high_risk_indicators && analysis.high_risk_indicators.length > 0) {
    insights.push({
      category: 'content',
      severity: 'high',
      title: 'High-Risk Content Patterns',
      description: `${analysis.high_risk_indicators.length} additional risk factor(s) identified`,
      recommendation: 'Review all flagged content patterns for potential security issues'
    });
  }

  return insights;
}

export function interpretTemporalPatterns(analysis: any): PatternInsight[] {
  const insights: PatternInsight[] = [];
  
  if (!analysis) return insights;

  const features = analysis.temporal_features || [];
  const featureNames = analysis.feature_names || [];

  // Check for high event rate
  const eventsPerMinute = features[featureNames.indexOf('events_per_minute_current')];
  if (eventsPerMinute > 1) {
    insights.push({
      category: 'temporal',
      severity: eventsPerMinute > 5 ? 'high' : 'medium',
      title: 'High Event Velocity',
      description: `${eventsPerMinute} events per minute detected`,
      recommendation: 'Verify if high-speed activity is expected or indicates automation'
    });
  }

  // Check baseline ratio
  const baselineRatio = features[featureNames.indexOf('events_per_minute_baseline_ratio')];
  if (baselineRatio > 3) {
    insights.push({
      category: 'temporal',
      severity: baselineRatio > 10 ? 'high' : 'medium',
      title: 'Activity Spike',
      description: `Current activity is ${baselineRatio.toFixed(1)}x above normal baseline`,
      recommendation: 'Investigate cause of activity spike and verify legitimacy'
    });
  }

  // Check off-hours intensity
  const offHoursIntensity = features[featureNames.indexOf('off_hours_intensity_ratio')];
  if (offHoursIntensity >= 1) {
    insights.push({
      category: 'temporal',
      severity: 'medium',
      title: 'Off-Hours Activity Concentration',
      description: 'Activity occurring entirely outside normal business hours',
      recommendation: 'Verify timezone alignment and expected work patterns'
    });
  }

  // Check detected patterns
  if (analysis.detected_patterns && analysis.detected_patterns.length > 0) {
    for (const pattern of analysis.detected_patterns) {
      insights.push({
        category: 'temporal',
        severity: 'medium',
        title: `${pattern.type.replace(/_/g, ' ')} Pattern`,
        description: pattern.description || `${pattern.type} temporal pattern detected`,
        technical_detail: `Confidence: ${pattern.confidence || 'N/A'}`
      });
    }
  }

  return insights;
}

export function createAnalysisBreakdown(
  behavioralAnalysis: any,
  contentAnalysis: any,
  temporalAnalysis: any,
  repositoryContext: any,
  detectionScores: any
): AnalysisBreakdown {
  const allInsights: PatternInsight[] = [
    ...interpretBehavioralPatterns(behavioralAnalysis),
    ...interpretContentPatterns(contentAnalysis),
    ...interpretTemporalPatterns(temporalAnalysis)
  ];

  // Sort by severity and score relevance
  allInsights.sort((a, b) => {
    const severityWeight = { high: 3, medium: 2, low: 1 };
    return severityWeight[b.severity] - severityWeight[a.severity];
  });

  // Determine primary reasons (top insights with high relevance)
  const primaryReasons = allInsights.filter(insight => 
    insight.severity === 'high' || 
    (insight.severity === 'medium' && allInsights.indexOf(insight) < 3)
  ).slice(0, 4);

  const supportingFactors = allInsights.filter(insight => 
    !primaryReasons.includes(insight)
  ).slice(0, 3);

  // Calculate overall confidence
  const scores = Object.values(detectionScores || {}) as number[];
  const maxScore = Math.max(...scores.filter(s => typeof s === 'number'));
  const confidence = Math.round(maxScore * 100);

  // Generate risk assessment
  const highSeverityCount = allInsights.filter(i => i.severity === 'high').length;
  let riskAssessment = '';
  
  if (highSeverityCount >= 3) {
    riskAssessment = 'Multiple high-risk patterns indicate potential security incident requiring immediate attention';
  } else if (highSeverityCount >= 1) {
    riskAssessment = 'Significant security concerns detected, warranting thorough investigation';
  } else if (allInsights.length >= 3) {
    riskAssessment = 'Unusual activity patterns detected, monitoring and review recommended';
  } else {
    riskAssessment = 'Anomalous behavior detected, standard security review suggested';
  }

  return {
    primary_reasons: primaryReasons,
    supporting_factors: supportingFactors,
    risk_assessment: riskAssessment,
    confidence
  };
}