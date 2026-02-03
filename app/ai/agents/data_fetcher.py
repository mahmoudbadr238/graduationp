"""
Data Fetch Agent
================
Executes tool calls and gathers evidence for analysis.

This agent takes the ToolPlan from the Planner and executes each tool call,
collecting the results as Evidence objects.

RESPONSIBILITIES:
1. Execute tool calls from the plan
2. Handle errors gracefully (continue on partial failures)
3. Collect all results into the Evidence structure
4. Track which tools succeeded vs failed
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from .schema import (
    ToolName,
    ToolCall,
    ToolPlan,
    EventEvidence,
    StatusEvidence,
    ScanEvidence,
    KBRuleEvidence,
    Evidence,
    AssistantState,
)
from .tools import ToolRegistry

logger = logging.getLogger(__name__)


# =============================================================================
# Data Fetch Agent
# =============================================================================

class DataFetchAgent:
    """
    Executes tool calls and gathers evidence.
    
    This agent uses the ToolRegistry to execute each tool call
    and collects the results into the Evidence structure.
    """
    
    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        self.tools = tool_registry or ToolRegistry()
        logger.info("DataFetchAgent initialized")
    
    def _execute_tool(
        self, 
        tool_call: ToolCall, 
        evidence: Evidence
    ) -> bool:
        """
        Execute a single tool call and add results to evidence.
        
        Returns True if successful, False otherwise.
        """
        tool = tool_call.tool
        args = tool_call.args
        
        try:
            if tool == ToolName.GET_RECENT_EVENTS:
                events, error = self.tools.get_recent_events(
                    limit=args.get('limit', 10),
                    severity_filter=args.get('level'),
                    log_name=args.get('log_names', [None])[0] if args.get('log_names') else None,
                )
                if error:
                    tool_call.error = error
                    evidence.errors.append(error)
                    return False
                for event in events:
                    evidence.events.append(self._event_to_evidence(event))
                tool_call.result = {"count": len(events)}
                tool_call.executed = True
                return True
            
            elif tool == ToolName.GET_EVENT_DETAILS:
                event_id = args.get('event_id')
                record_id = args.get('record_id')
                if not event_id and not record_id:
                    logger.warning("GET_EVENT_DETAILS called without event_id or record_id")
                    tool_call.error = "Missing event_id or record_id"
                    return False
                event, error = self.tools.get_event_details(
                    record_id=record_id,
                    event_id=event_id,
                )
                if error:
                    tool_call.error = error
                    return False
                if event:
                    evidence.events.append(self._event_to_evidence(event))
                    tool_call.result = {"found": True, "event_id": event.event_id}
                    tool_call.executed = True
                    return True
                else:
                    tool_call.error = "Event not found"
                    return False
            
            elif tool == ToolName.SEARCH_EVENTS:
                # Build a search query from params
                query_parts = []
                if args.get('event_ids'):
                    query_parts.append(f"event_id:{args['event_ids'][0]}")
                if args.get('level'):
                    query_parts.append(f"level:{args['level']}")
                if args.get('providers'):
                    query_parts.append(f"provider:{args['providers'][0]}")
                query = " ".join(query_parts) if query_parts else "*"
                
                events, error = self.tools.search_events(
                    query=query,
                    limit=args.get('limit', 20),
                )
                if error:
                    tool_call.error = error
                    evidence.errors.append(error)
                    return False
                for event in events:
                    evidence.events.append(self._event_to_evidence(event))
                tool_call.result = {"count": len(events)}
                tool_call.executed = True
                return True
            
            elif tool == ToolName.GET_FIREWALL_STATUS:
                status, error = self.tools.get_firewall_status()
                if error:
                    tool_call.error = error
                    evidence.errors.append(error)
                evidence.statuses.append(StatusEvidence(
                    name="firewall",
                    value={
                        "domain": status.domain,
                        "private": status.private,
                        "public": status.public,
                    },
                    is_healthy=status.all_enabled,
                    issues=self._get_firewall_issues(status),
                ))
                tool_call.result = {"all_enabled": status.all_enabled}
                tool_call.executed = True
                return True
            
            elif tool == ToolName.GET_DEFENDER_STATUS:
                status, error = self.tools.get_defender_status()
                if error:
                    tool_call.error = error
                    evidence.errors.append(error)
                evidence.statuses.append(StatusEvidence(
                    name="defender",
                    value={
                        "realtime_protection": status.realtime_protection,
                        "tamper_protection": status.tamper_protection,
                        "last_scan": status.last_scan,
                        "antivirus_enabled": status.antivirus_enabled,
                    },
                    is_healthy=status.is_healthy,
                    issues=self._get_defender_issues(status),
                ))
                tool_call.result = {"realtime_protection": status.realtime_protection}
                tool_call.executed = True
                return True
            
            elif tool == ToolName.GET_UPDATE_STATUS:
                status, error = self.tools.get_update_status()
                if error:
                    tool_call.error = error
                    evidence.errors.append(error)
                is_healthy = status.pending_updates < 5 and not status.pending_reboot
                evidence.statuses.append(StatusEvidence(
                    name="updates",
                    value={
                        "pending_updates": status.pending_updates,
                        "pending_reboot": status.pending_reboot,
                        "last_update": status.last_update,
                    },
                    is_healthy=is_healthy,
                    issues=self._get_update_issues(status),
                ))
                tool_call.result = {"pending": status.pending_updates}
                tool_call.executed = True
                return True
            
            elif tool == ToolName.SCAN_FILE:
                file_path = args.get('file_path')
                if not file_path:
                    logger.warning("SCAN_FILE called without file_path")
                    tool_call.error = "Missing file_path"
                    return False
                result, error = self.tools.scan_file(file_path)
                if error:
                    tool_call.error = error
                    evidence.errors.append(error)
                evidence.scans.append(ScanEvidence(
                    scan_type="file",
                    target=file_path,
                    verdict=result.verdict,
                    score=result.score,
                    signals=result.signals,
                    details={
                        "hashes": result.hashes,
                    },
                ))
                tool_call.result = {"verdict": result.verdict, "score": result.score}
                tool_call.executed = True
                return True
            
            elif tool == ToolName.ANALYZE_URL_OFFLINE:
                url = args.get('url')
                if not url:
                    logger.warning("ANALYZE_URL_OFFLINE called without url")
                    tool_call.error = "Missing url"
                    return False
                result, error = self.tools.analyze_url_offline(url)
                if error:
                    tool_call.error = error
                    evidence.errors.append(error)
                evidence.scans.append(ScanEvidence(
                    scan_type="url_offline",
                    target=url,
                    verdict=result.verdict,
                    score=result.score,
                    signals=result.signals,
                    details={
                        "whois": result.whois,
                        "dns": result.dns,
                    },
                ))
                tool_call.result = {"verdict": result.verdict}
                tool_call.executed = True
                return True
            
            elif tool == ToolName.ANALYZE_URL_ONLINE:
                url = args.get('url')
                if not url:
                    logger.warning("ANALYZE_URL_ONLINE called without url")
                    tool_call.error = "Missing url"
                    return False
                result, error = self.tools.analyze_url_online(url)
                if error:
                    tool_call.error = error
                    # Online is optional, don't fail
                    return False
                evidence.scans.append(ScanEvidence(
                    scan_type="url_online",
                    target=url,
                    verdict=result.verdict,
                    score=result.score,
                    signals=result.signals,
                    details={
                        "source": "online_api",
                    },
                ))
                tool_call.result = {"verdict": result.verdict}
                tool_call.executed = True
                return True
            
            elif tool == ToolName.LOOKUP_KB_RULES:
                event_ids = args.get('event_ids', [])
                if not event_ids:
                    # Try to get event IDs from already-collected evidence
                    event_ids = [e.event_id for e in evidence.events]
                
                if event_ids:
                    # Lookup each event in the KB
                    matched_count = 0
                    for event in evidence.events:
                        # Try lookup with provider and event_id
                        rule, error = self.tools.lookup_kb_rules(
                            provider=event.provider,
                            event_id=event.event_id,
                        )
                        if rule:
                            event.kb_matched = True
                            event.kb_title = rule.get('title', '')
                            event.kb_severity = rule.get('severity', '')
                            event.kb_impact = rule.get('impact', '')
                            event.kb_causes = rule.get('causes', [])
                            event.kb_actions = rule.get('actions', [])
                            matched_count += 1
                    
                    tool_call.result = {"matched_count": matched_count}
                    tool_call.executed = True
                    return True
                else:
                    tool_call.error = "No event IDs to lookup"
                    return False
            
            elif tool == ToolName.GET_APP_HELP:
                topic = args.get('topic', 'general')
                help_info, error = self.tools.get_app_help(topic)
                if error:
                    tool_call.error = error
                evidence.statuses.append(StatusEvidence(
                    name="app_help",
                    value={"text": help_info or "Help not available"},
                    is_healthy=True,
                    issues=[],
                ))
                tool_call.result = {"topic": topic}
                tool_call.executed = True
                return True
            
            else:
                logger.warning(f"Unknown tool: {tool}")
                tool_call.error = f"Unknown tool: {tool.value}"
                return False
                
        except Exception as e:
            logger.error(f"Error executing tool {tool.value}: {e}", exc_info=True)
            tool_call.error = str(e)
            evidence.errors.append(f"{tool.value}: {str(e)}")
            return False
    
    def _event_to_evidence(self, event) -> EventEvidence:
        """Convert a raw Event to EventEvidence."""
        return EventEvidence(
            record_id=getattr(event, 'record_id', 0),
            log_name=getattr(event, 'log_name', getattr(event, 'source', 'Unknown')),
            provider=getattr(event, 'provider', ''),
            event_id=event.event_id,
            level=event.level,
            time_created=getattr(event, 'time_created', getattr(event, 'timestamp', '')),
            message=event.message or '',
            fields=getattr(event, 'additional_data', {}) or {},
        )
    
    def _get_firewall_issues(self, status) -> List[str]:
        """Identify issues from firewall status."""
        issues = []
        if not status.all_enabled:
            if not status.domain:
                issues.append("Domain firewall profile is disabled")
            if not status.private:
                issues.append("Private firewall profile is disabled")
            if not status.public:
                issues.append("Public firewall profile is disabled - highest risk")
        return issues
    
    def _get_defender_issues(self, status) -> List[str]:
        """Identify issues from Defender status."""
        issues = []
        if not status.realtime_protection:
            issues.append("Real-time protection is disabled")
        if not status.antivirus_enabled:
            issues.append("Antivirus is disabled")
        return issues
    
    def _get_update_issues(self, status) -> List[str]:
        """Identify issues from update status."""
        issues = []
        if status.pending_reboot:
            issues.append("System requires a reboot to complete updates")
        if status.pending_updates > 5:
            issues.append(f"{status.pending_updates} updates pending")
        return issues
    
    def run(self, state: AssistantState) -> AssistantState:
        """
        Run the data fetch agent on the current state.
        
        Updates state with:
        - evidence: Evidence object with all gathered data
        """
        # Initialize evidence if needed
        if not state.evidence:
            state.evidence = Evidence()
        
        if not state.plan or not state.plan.calls:
            logger.info("No tools to execute")
            return state
        
        executed_count = 0
        failed_count = 0
        
        # Execute tools in order
        for tool_call in state.plan.calls:
            logger.info(f"Executing tool: {tool_call.tool.value}")
            
            success = self._execute_tool(tool_call, state.evidence)
            
            if success:
                executed_count += 1
                logger.info(f"Tool {tool_call.tool.value} succeeded")
            else:
                failed_count += 1
                logger.warning(f"Tool {tool_call.tool.value} failed: {tool_call.error}")
        
        logger.info(
            f"Data fetch complete: {executed_count} succeeded, {failed_count} failed, "
            f"evidence: {len(state.evidence.events)} events, "
            f"{len(state.evidence.statuses)} statuses, {len(state.evidence.scans)} scans"
        )
        
        return state


# =============================================================================
# Factory Function
# =============================================================================

def create_data_fetcher(tool_registry: Optional[ToolRegistry] = None) -> DataFetchAgent:
    """Create a DataFetchAgent instance."""
    return DataFetchAgent(tool_registry)
