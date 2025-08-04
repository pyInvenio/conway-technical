import json
from typing import List, Dict, Any, Optional
import aiohttp
import logging
import hashlib
from datetime import datetime, timedelta

from ...config import settings
from ..models.anomaly_score import AnomalyScore, SeverityLevel

logger = logging.getLogger(__name__)

class TieredAISummarizer:
    """Cost-optimized AI summarization system with tiered processing"""
    
    def __init__(self, redis_client=None):
        self.use_ai = bool(settings.openai_api_key)
        self.redis_client = redis_client
        
        # Tiered processing configuration
        self.tier_config = {
            'tier_1': {  # Critical/High - Full AI analysis
                'severity_levels': [SeverityLevel.CRITICAL, SeverityLevel.HIGH],
                'max_tokens': 500,
                'use_full_context': True,
                'cache_ttl': 3600  # 1 hour
            },
            'tier_2': {  # Medium - Filtered context AI
                'severity_levels': [SeverityLevel.MEDIUM],
                'max_tokens': 200,
                'use_full_context': False,
                'cache_ttl': 7200  # 2 hours
            },
            'tier_3': {  # Low - Rule-based with minimal AI
                'severity_levels': [SeverityLevel.LOW],
                'max_tokens': 50,
                'use_full_context': False,
                'cache_ttl': 14400  # 4 hours
            },
            'tier_4': {  # Info - Pure rule-based
                'severity_levels': [SeverityLevel.INFO],
                'max_tokens': 0,
                'use_full_context': False,
                'cache_ttl': 86400  # 24 hours
            }
        }
        
        # Context templates for efficient token usage
        self.context_templates = {
            'force_push': ['commit_messages', 'branch_info', 'diff_stats', 'actor_info'],
            'workflow_failure': ['build_logs_summary', 'changed_files', 'error_patterns', 'failure_count'],
            'secret_exposure': ['file_paths', 'commit_diff', 'secret_types', 'user_history'],
            'mass_deletion': ['deleted_items', 'actor_patterns', 'time_distribution'],
            'bursty_activity': ['event_rates', 'actor_distribution', 'time_patterns'],
            'anomalous_activity': ['entropy_details', 'pattern_deviations', 'statistical_outliers']
        }
        
    async def generate_summary(
        self, 
        events: List[Any], 
        anomaly_score: AnomalyScore,
        context_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate tiered incident summary based on severity level"""
        
        # Determine processing tier
        tier = self._get_processing_tier(anomaly_score.severity_level)
        tier_config = self.tier_config[tier]
        
        # Check cache first
        cache_key = self._generate_cache_key(anomaly_score, context_data)
        if self.redis_client:
            cached_summary = await self._get_cached_summary(cache_key)
            if cached_summary:
                logger.info(f"Using cached summary for {anomaly_score.incident_type} (tier: {tier})")
                return cached_summary
        
        # Generate summary based on tier
        if tier == 'tier_4' or not self.use_ai:
            # Pure rule-based for INFO level or when AI unavailable
            summary = self._rule_based_summary(anomaly_score, context_data)
        else:
            try:
                # AI-powered with tier-specific optimization
                summary = await self._tiered_ai_summary(
                    events, anomaly_score, context_data, tier_config
                )
            except Exception as e:
                logger.error(f"AI summarization failed for tier {tier}: {e}")
                summary = self._rule_based_summary(anomaly_score, context_data)
        
        # Cache the result
        if self.redis_client:
            await self._cache_summary(cache_key, summary, tier_config['cache_ttl'])
        
        # Add cost optimization metadata
        summary['_metadata'] = {
            'processing_tier': tier,
            'estimated_tokens': tier_config['max_tokens'],
            'cache_used': bool(cached_summary),
            'generated_at': datetime.utcnow().isoformat()
        }
        
        return summary
    
    def _get_processing_tier(self, severity_level: SeverityLevel) -> str:
        """Determine processing tier based on severity level"""
        for tier, config in self.tier_config.items():
            if severity_level in config['severity_levels']:
                return tier
        return 'tier_4'  # Default to rule-based
    
    def _generate_cache_key(self, anomaly_score: AnomalyScore, context_data: Optional[Dict[str, Any]]) -> str:
        """Generate cache key for similarity matching"""
        # Create hash from incident type, severity range, and key context
        severity_range = f"{anomaly_score.severity_level.level_name}"
        context_hash = ""
        
        if context_data:
            # Hash only relevant context fields to improve cache hits
            relevant_context = {
                'incident_type': anomaly_score.incident_type,
                'repo_type': context_data.get('repository_info', {}).get('visibility', 'unknown'),
                'branch_type': 'main' if any(b in context_data.get('ref', '') 
                                           for b in ['main', 'master']) else 'feature',
                'actor_count': min(len(context_data.get('unique_actors', [])), 5)  # Cap for grouping
            }
            context_str = json.dumps(relevant_context, sort_keys=True)
            context_hash = hashlib.md5(context_str.encode()).hexdigest()[:8]
        
        return f"ai_summary:{anomaly_score.incident_type}:{severity_range}:{context_hash}"
    
    async def _get_cached_summary(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached summary"""
        try:
            cached = await self.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache retrieval failed: {e}")
        return None
    
    async def _cache_summary(self, cache_key: str, summary: Dict[str, Any], ttl: int):
        """Cache summary with TTL"""
        try:
            await self.redis_client.setex(
                cache_key, 
                ttl, 
                json.dumps(summary, default=str)
            )
        except Exception as e:
            logger.warning(f"Cache storage failed: {e}")
    
    async def _tiered_ai_summary(
        self, 
        events: List[Any], 
        anomaly_score: AnomalyScore,
        context_data: Optional[Dict[str, Any]],
        tier_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate AI summary with tier-specific optimizations"""
        
        # Compress context based on tier and incident type
        compressed_context = self._compress_context(
            anomaly_score.incident_type,
            context_data or {},
            tier_config['use_full_context']
        )
        
        # Build tier-appropriate prompt
        prompt = self._build_tiered_prompt(
            anomaly_score, 
            compressed_context, 
            tier_config['max_tokens']
        )
        
        # Determine model based on tier
        model = "gpt-4o-mini" if tier_config['max_tokens'] <= 200 else "gpt-4o"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": tier_config['max_tokens'],
                        "response_format": {"type": "json_object"}
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = json.loads(data["choices"][0]["message"]["content"])
                        
                        # Add token usage tracking
                        usage = data.get("usage", {})
                        result['_token_usage'] = {
                            'prompt_tokens': usage.get('prompt_tokens', 0),
                            'completion_tokens': usage.get('completion_tokens', 0),
                            'total_tokens': usage.get('total_tokens', 0)
                        }
                        
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"OpenAI API error: {response.status}. {error_text}")
                        if response.status == 429:
                            logger.warning("OpenAI rate limit hit, using rule-based summary")
                        raise Exception(f"API error: {response.status}")
                        
        except Exception as e:
            logger.error(f"AI summary error: {e}")
            raise
    
    def _compress_context(
        self, 
        incident_type: str, 
        context_data: Dict[str, Any], 
        use_full_context: bool
    ) -> Dict[str, Any]:
        """Compress context data based on incident type and tier settings"""
        
        if use_full_context:
            return context_data
        
        # Get relevant fields for this incident type
        relevant_fields = self.context_templates.get(incident_type, ['basic_info'])
        compressed = {}
        
        # Extract only relevant context
        for field in relevant_fields:
            if field == 'commit_messages' and 'commits' in context_data:
                # Summarize commit messages
                commits = context_data['commits'][:3]  # Limit to first 3
                compressed['recent_commits'] = [c.get('message', '')[:100] for c in commits]
            
            elif field == 'branch_info':
                compressed['branch'] = context_data.get('ref', 'unknown')
                compressed['is_protected'] = any(b in context_data.get('ref', '').lower() 
                                               for b in ['main', 'master', 'prod'])
            
            elif field == 'actor_info':
                actors = context_data.get('unique_actors', [])
                compressed['actor_count'] = len(actors)
                compressed['primary_actor'] = actors[0] if actors else 'unknown'
            
            elif field == 'error_patterns' and 'failures' in context_data:
                failures = context_data['failures'][:2]  # Limit failures
                compressed['error_types'] = [f.get('conclusion', 'unknown') for f in failures]
            
            elif field == 'event_rates':
                compressed['events_per_minute'] = context_data.get('events_per_minute', 0)
                compressed['total_events'] = context_data.get('event_count', 0)
            
            elif field in context_data:
                compressed[field] = context_data[field]
        
        return compressed
    
    def _build_tiered_prompt(
        self, 
        anomaly_score: AnomalyScore, 
        context: Dict[str, Any], 
        max_tokens: int
    ) -> str:
        """Build tier-appropriate prompt for AI summarization"""
        
        if max_tokens >= 400:  # Tier 1 - Full analysis
            return f"""Analyze this GitHub security incident comprehensively.

Incident: {anomaly_score.incident_type}
Severity: {anomaly_score.final_score:.2f} ({anomaly_score.severity_level.level_name})
Context: {json.dumps(context, indent=2)}

Provide detailed JSON with:
- "title": Descriptive incident title (max 120 chars)
- "root_cause": Array of 4-6 detailed root cause points
- "impact": Array of 4-6 impact assessment points  
- "next_steps": Array of 5-7 specific actionable steps
- "threat_level": Overall threat assessment
- "recommendations": Long-term security recommendations

Focus on security implications, technical details, and comprehensive response strategy."""
        
        elif max_tokens >= 150:  # Tier 2 - Focused analysis
            return f"""Analyze this GitHub security incident.

Type: {anomaly_score.incident_type}
Severity: {anomaly_score.final_score:.2f}
Key Context: {json.dumps(context)}

Provide JSON with:
- "title": Incident title (max 100 chars)
- "root_cause": Array of 3 key root causes
- "impact": Array of 3 main impacts
- "next_steps": Array of 4 immediate actions

Focus on essential security concerns and immediate response needs."""
        
        else:  # Tier 3 - Minimal AI enhancement
            return f"""Briefly analyze: {anomaly_score.incident_type} (severity: {anomaly_score.final_score:.2f})

Context: {str(context)[:200]}

Provide concise JSON:
- "title": Brief title (max 80 chars)
- "summary": 2-sentence impact summary
- "actions": Array of 2 immediate actions"""
    
    def _rule_based_summary(
        self, 
        anomaly_score: AnomalyScore, 
        context_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate rule-based summary for all severity levels"""
        
        incident_type = anomaly_score.incident_type
        severity = anomaly_score.final_score
        repo_name = context_data.get('repo_name', 'Unknown') if context_data else 'Unknown'
        
        # Streamlined rule-based templates
        templates = {
            "force_push": {
                "title": f"Force push detected on {repo_name}",
                "root_cause": ["Force push operation detected", f"Severity: {severity:.2f}", "Potential history rewrite"],
                "impact": ["Git history compromised", "Team sync issues", "CI/CD disruption"],
                "next_steps": ["Review forced commits", "Check backups", "Notify team", "Add branch protection"]
            },
            "workflow_failure": {
                "title": f"Multiple workflow failures in {repo_name}",
                "root_cause": ["CI/CD failures detected", f"Severity: {severity:.2f}", "Systematic build issues"],
                "impact": ["Deployment blocked", "Quality checks bypassed", "Security gaps"],
                "next_steps": ["Check failure logs", "Review recent commits", "Verify config", "Run security scans"]
            },
            "secret_exposure": {
                "title": f"Potential secret exposure in {repo_name}",
                "root_cause": ["Secret patterns detected", f"Severity: {severity:.2f}", "Credential leak risk"],
                "impact": ["Credential compromise", "Unauthorized access", "Data breach risk"],
                "next_steps": ["Rotate credentials", "Remove secrets", "Audit access", "Implement secret scanning"]
            },
            "mass_deletion": {
                "title": f"Mass deletion event in {repo_name}",
                "root_cause": ["Multiple deletions detected", f"Severity: {severity:.2f}", "Data loss risk"],
                "impact": ["Code/docs lost", "Project disruption", "Recovery needed"],
                "next_steps": ["Check deletions", "Verify backups", "Review actor", "Consider access revocation"]
            },
            "bursty_activity": {
                "title": f"Anomalous activity burst in {repo_name}",
                "root_cause": ["Activity spike detected", f"Severity: {severity:.2f}", "Automated/coordinated pattern"],
                "impact": ["Potential attack", "Operations disrupted", "Audit trail flooded"],
                "next_steps": ["Review actor patterns", "Check API tokens", "Implement rate limits", "Audit changes"]
            },
            "anomalous_activity": {
                "title": f"High entropy anomaly in {repo_name}",
                "root_cause": ["Unusual activity pattern", f"Severity: {severity:.2f}", "Unknown threat type"],
                "impact": ["Unknown impact", "Potential zero-day", "Integrity unclear"],
                "next_steps": ["Manual analysis", "Pattern investigation", "Close monitoring", "Access restrictions"]
            }
        }
        
        # Get template and add context-specific details
        template = templates.get(incident_type, templates["anomalous_activity"])
        
        # Add severity-specific enhancements
        if severity >= 0.85:  # Critical
            template["urgency"] = "CRITICAL - Immediate action required"
            template["escalation"] = "Auto-escalated to security team"
        elif severity >= 0.65:  # High
            template["urgency"] = "HIGH - Review within 1 hour"
        elif severity >= 0.45:  # Medium
            template["urgency"] = "MEDIUM - Review within 4 hours"
        else:  # Low/Info
            template["urgency"] = "LOW - Review within 24 hours"
        
        return template
    
    async def get_cost_statistics(self) -> Dict[str, Any]:
        """Get cost optimization statistics"""
        # This would typically query Redis for usage stats
        stats = {
            'tier_usage': {
                'tier_1_requests': 0,  # Would be populated from Redis
                'tier_2_requests': 0,
                'tier_3_requests': 0,
                'tier_4_requests': 0
            },
            'token_savings': {
                'estimated_tokens_saved': 0,  # vs always using full AI
                'cache_hit_rate': 0.0,
                'cost_savings_usd': 0.0
            },
            'summary': {
                'total_requests': 0,
                'ai_requests': 0,
                'rule_based_requests': 0,
                'avg_tokens_per_request': 0
            }
        }
        return stats
