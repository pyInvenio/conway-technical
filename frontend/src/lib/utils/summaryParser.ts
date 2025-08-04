/**
 * Summary Parser Utility
 * Extracts structured summaries from AI-generated anomaly data
 */

export interface ParsedSummary {
  title: string;
  root_cause: string[];
  impact: string[];
  next_steps: string[];
  threat_level?: string;
  incident_type?: string;
  urgency?: string;
  recommendations?: string[];
}

export interface ComponentScores {
  behavioral: number;
  content: number;
  temporal: number;
  repository: number;
}

export interface RiskIndicators {
  indicators: string[];
  severity: string;
  confidence: number;
}

/**
 * Parse AI summary field which may contain JSON or text
 */
export function parseAISummary(aiSummary: string | null): ParsedSummary | null {
  if (!aiSummary) return null;

  // Try to parse as JSON first
  try {
    const parsed = JSON.parse(aiSummary);
    
    // Validate structure
    if (typeof parsed === 'object' && parsed !== null) {
      return {
        title: parsed.title || 'Security Incident Detected',
        root_cause: Array.isArray(parsed.root_cause) ? parsed.root_cause : 
                   parsed.root_cause ? [parsed.root_cause] : [],
        impact: Array.isArray(parsed.impact) ? parsed.impact : 
               parsed.impact ? [parsed.impact] : [],
        next_steps: Array.isArray(parsed.next_steps) ? parsed.next_steps : 
                   parsed.next_steps ? [parsed.next_steps] : [],
        threat_level: parsed.threat_level,
        incident_type: parsed.incident_type,
        urgency: parsed.urgency,
        recommendations: Array.isArray(parsed.recommendations) ? parsed.recommendations : undefined
      };
    }
  } catch (e) {
    // Not valid JSON, continue to text parsing
  }

  // If not JSON, try to extract from text format
  return parseTextSummary(aiSummary);
}

/**
 * Extract structured data from text-based AI summaries
 */
function parseTextSummary(text: string): ParsedSummary | null {
  const lines = text.split('\n').map(line => line.trim()).filter(line => line.length > 0);
  
  const result: ParsedSummary = {
    title: 'Security Incident Analysis',
    root_cause: [],
    impact: [],
    next_steps: []
  };

  let currentSection: keyof ParsedSummary | null = null;
  
  for (const line of lines) {
    // Detect section headers
    if (line.toLowerCase().includes('root cause') || line.toLowerCase().includes('causes:')) {
      currentSection = 'root_cause';
      continue;
    } else if (line.toLowerCase().includes('impact')) {
      currentSection = 'impact';
      continue;
    } else if (line.toLowerCase().includes('next steps') || line.toLowerCase().includes('actions:')) {
      currentSection = 'next_steps';
      continue;
    } else if (line.toLowerCase().includes('title:')) {
      result.title = line.replace(/title:\s*/i, '');
      continue;
    }

    // Extract bullet points or numbered items
    if (line.match(/^[-•*]\s+/) || line.match(/^\d+\.\s+/)) {
      const content = line.replace(/^[-•*]\s+/, '').replace(/^\d+\.\s+/, '');
      if (currentSection && Array.isArray(result[currentSection])) {
        (result[currentSection] as string[]).push(content);
      }
    }
  }

  // If we found any structured content, return it
  if (result.root_cause.length > 0 || result.impact.length > 0 || result.next_steps.length > 0) {
    return result;
  }

  return null;
}

/**
 * Parse high risk indicators JSON field
 */
export function parseRiskIndicators(indicators: any): RiskIndicators {
  if (Array.isArray(indicators)) {
    return {
      indicators: indicators.filter(i => typeof i === 'string'),
      severity: 'medium',
      confidence: 0.8
    };
  }

  if (typeof indicators === 'object' && indicators !== null) {
    return {
      indicators: Array.isArray(indicators.indicators) ? indicators.indicators : [],
      severity: indicators.severity || 'medium',
      confidence: indicators.confidence || 0.8
    };
  }

  return {
    indicators: [],
    severity: 'low',
    confidence: 0.5
  };
}

/**
 * Generate incident type display name
 */
export function getIncidentTypeDisplay(eventType: string): string {
  const typeMap: Record<string, string> = {
    'PushEvent': 'Force Push Detection',
    'WorkflowRunEvent': 'Workflow Failure',
    'DeleteEvent': 'Mass Deletion',
    'MemberEvent': 'Access Change',
    'ReleaseEvent': 'Release Anomaly',
    'ForkEvent': 'Suspicious Fork',
    'IssuesEvent': 'Issue Burst',
    'PullRequestEvent': 'PR Anomaly',
    'force_push': 'Force Push to Main',
    'workflow_failure': 'CI/CD Failure',
    'secret_exposure': 'Secret Exposure',
    'mass_deletion': 'Mass Deletion',
    'bursty_activity': 'Activity Burst',
    'anomalous_activity': 'Anomalous Pattern'
  };

  return typeMap[eventType] || 'Security Alert';
}

/**
 * Get severity color class based on score
 */
export function getSeverityColor(severity: string | number): string {
  const score = typeof severity === 'string' ? 
    (severity === 'CRITICAL' ? 1.0 : 
     severity === 'HIGH' ? 0.8 : 
     severity === 'MEDIUM' ? 0.6 : 
     severity === 'LOW' ? 0.4 : 0.2) : severity;

  if (score >= 0.8) return 'text-red-400';
  if (score >= 0.6) return 'text-orange-400';
  if (score >= 0.4) return 'text-yellow-400';
  return 'text-blue-400';
}

/**
 * Get detection method from component scores
 */
export function getPrimaryDetectionMethod(scores: ComponentScores): { method: string; score: number; description: string } {
  console.log('getPrimaryDetectionMethod input scores:', scores);
  
  const methods = [
    { key: 'behavioral', method: 'Behavioral Analysis', description: 'Unusual user/repository behavior patterns' },
    { key: 'content', method: 'Content Analysis', description: 'Suspicious code or data patterns' },
    { key: 'temporal', method: 'Temporal Analysis', description: 'Time-based anomaly detection' },
    { key: 'repository', method: 'Repository Analysis', description: 'Repository criticality assessment' }
  ];

  // Convert scores to numbers and handle null/undefined
  const normalizedScores = {
    behavioral: Number(scores.behavioral) || 0,
    content: Number(scores.content) || 0,
    temporal: Number(scores.temporal) || 0,
    repository: Number(scores.repository) || 0
  };

  console.log('Normalized scores:', normalizedScores);

  // Find the method with the highest score
  let highest = methods[0]; // Default to behavioral
  let maxScore = normalizedScores.behavioral;

  // Check each method to find the highest score
  methods.forEach(method => {
    const score = normalizedScores[method.key as keyof ComponentScores];
    console.log(`Checking ${method.key}: ${score} vs current max: ${maxScore}`);
    if (score > maxScore) {
      highest = method;
      maxScore = score;
      console.log(`New highest: ${method.key} with score ${score}`);
    }
  });

  // If all scores are very low or zero, classify based on any non-zero score
  if (maxScore <= 0.1) {
    console.log('All scores very low, using fallback logic');
    // Find any method with a non-zero score
    for (const method of methods) {
      const score = normalizedScores[method.key as keyof ComponentScores];
      if (score > 0) {
        highest = method;
        maxScore = score;
        break;
      }
    }
  }

  const result = {
    method: highest.method,
    score: maxScore,
    description: highest.description
  };

  console.log('getPrimaryDetectionMethod result:', result);
  return result;
}

/**
 * Format summary
 */
export function formatTechnicalSummary(summary: ParsedSummary): ParsedSummary {
  return {
    ...summary,
    root_cause: summary.root_cause.slice(0, 5), // Max 5 bullets
    impact: summary.impact.slice(0, 5),
    next_steps: summary.next_steps.slice(0, 5)
  };
}

/**
 * Generate fallback summary for anomalies without structured AI data
 */
export function generateFallbackSummary(
  eventType: string, 
  severity: string | number, 
  repositoryName: string,
  componentScores: ComponentScores
): ParsedSummary {
  const incidentType = getIncidentTypeDisplay(eventType);
  const primaryMethod = getPrimaryDetectionMethod(componentScores);
  
  const templates: Record<string, Partial<ParsedSummary>> = {
    'PushEvent': {
      root_cause: [
        'Force push operation detected on protected branch',
        `Anomaly score: ${typeof severity === 'number' ? (severity * 100).toFixed(0) : severity}%`,
        'Potential git history rewrite or unauthorized changes'
      ],
      impact: [
        'Repository integrity compromised',
        'Team synchronization issues',
        'CI/CD pipeline disruption',
        'Potential loss of commit history'
      ],
      next_steps: [
        'Review forced push commits immediately',
        'Verify repository backup integrity',
        'Notify development team',
        'Implement branch protection rules',
        'Audit user permissions'
      ]
    },
    'WorkflowRunEvent': {
      root_cause: [
        'Multiple CI/CD workflow failures detected',
        `Failure pattern severity: ${typeof severity === 'number' ? (severity * 100).toFixed(0) : severity}%`,
        'Systematic build or test failures'
      ],
      impact: [
        'Deployment pipeline blocked',
        'Code quality checks bypassed',
        'Security scan failures',
        'Production deployment risks'
      ],
      next_steps: [
        'Investigate workflow failure logs',
        'Review recent commits for issues',
        'Verify configuration changes',
        'Run manual security scans',
        'Check dependencies for vulnerabilities'
      ]
    }
  };

  const template = templates[eventType] || {
    root_cause: [
      `${incidentType} detected in repository`,
      `Detection method: ${primaryMethod.method}`,
      `Anomaly confidence: ${(primaryMethod.score * 100).toFixed(0)}%`
    ],
    impact: [
      'Potential security implications',
      'Repository monitoring flagged unusual activity',
      'Requires manual investigation'
    ],
    next_steps: [
      'Review event details and context',
      'Analyze user activity patterns',
      'Check for related suspicious events',
      'Consider access restrictions if needed'
    ]
  };

  return {
    title: `${incidentType} in ${repositoryName}`,
    root_cause: template.root_cause || [],
    impact: template.impact || [],
    next_steps: template.next_steps || [],
    incident_type: incidentType,
    threat_level: typeof severity === 'number' ? 
      (severity >= 0.8 ? 'CRITICAL' : severity >= 0.6 ? 'HIGH' : 'MEDIUM') : 
      severity
  };
}