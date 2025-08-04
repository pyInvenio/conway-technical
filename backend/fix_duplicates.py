#!/usr/bin/env python3
"""
Script to fix duplicate event assignments in incidents.
Each event should belong to at most one incident.
"""

import json
from collections import defaultdict
from app.database import SessionLocal
from app.models import GitHubEvent, IncidentSummary

def fix_duplicate_events():
    """Fix duplicate event assignments."""
    db = SessionLocal()
    
    try:
        # Find all incidents
        incidents = db.query(IncidentSummary).all()
        print(f"Processing {len(incidents)} incidents...")
        
        # Track which events belong to which incidents
        event_to_incidents = defaultdict(list)
        
        for incident in incidents:
            if incident.event_ids:
                for event_id in incident.event_ids:
                    event_to_incidents[event_id].append(incident.id)
        
        # Find duplicates
        duplicate_events = {event_id: incident_ids 
                          for event_id, incident_ids in event_to_incidents.items() 
                          if len(incident_ids) > 1}
        
        print(f"Found {len(duplicate_events)} events with duplicate assignments")
        
        # Fix duplicates by assigning each event to the earliest incident
        for event_id, incident_ids in duplicate_events.items():
            primary_incident_id = min(incident_ids)
            
            print(f"Event {event_id}: assigning to incident {primary_incident_id}, removing from {incident_ids[1:]}")
            
            # Update the event's incident_id
            db.query(GitHubEvent).filter(GitHubEvent.id == event_id).update({
                "incident_id": primary_incident_id
            })
            
            # Remove from other incidents
            for incident_id in incident_ids:
                if incident_id != primary_incident_id:
                    incident = db.query(IncidentSummary).filter(IncidentSummary.id == incident_id).first()
                    if incident and incident.event_ids:
                        # Remove event_id from the array
                        new_event_ids = [eid for eid in incident.event_ids if eid != event_id]
                        incident.event_ids = new_event_ids
        
        # Assign incident_id to events that don't have duplicates
        single_events = {event_id: incident_ids[0] 
                        for event_id, incident_ids in event_to_incidents.items() 
                        if len(incident_ids) == 1}
        
        print(f"Assigning incident_id to {len(single_events)} non-duplicate events")
        
        for event_id, incident_id in single_events.items():
            db.query(GitHubEvent).filter(GitHubEvent.id == event_id).update({
                "incident_id": incident_id
            })
        
        # Remove incidents with no events
        incidents_to_remove = []
        for incident in incidents:
            if not incident.event_ids or len(incident.event_ids) == 0:
                incidents_to_remove.append(incident.id)
                db.delete(incident)
        
        if incidents_to_remove:
            print(f"Removing {len(incidents_to_remove)} empty incidents: {incidents_to_remove}")
        
        # Commit all changes
        db.commit()
        print("✅ Duplicate cleanup completed successfully!")
        
        # Verify results
        remaining_duplicates = defaultdict(list)
        incidents = db.query(IncidentSummary).all()
        
        for incident in incidents:
            if incident.event_ids:
                for event_id in incident.event_ids:
                    remaining_duplicates[event_id].append(incident.id)
        
        still_duplicate = {event_id: incident_ids 
                          for event_id, incident_ids in remaining_duplicates.items() 
                          if len(incident_ids) > 1}
        
        if still_duplicate:
            print(f"⚠️  Warning: {len(still_duplicate)} events still have duplicates")
        else:
            print("✅ No remaining duplicates found")
            
        # Count events with incident_id assigned
        events_with_incident = db.query(GitHubEvent).filter(GitHubEvent.incident_id.isnot(None)).count()
        total_events = db.query(GitHubEvent).count()
        
        print(f"📊 {events_with_incident}/{total_events} events now have incident_id assigned")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    fix_duplicate_events()