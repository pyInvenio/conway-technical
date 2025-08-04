# app/cleanup.py
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from sqlalchemy import text, func
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import GitHubEvent, AnomalyDetection
from .config import settings

logger = logging.getLogger(__name__)

class DatabaseCleanup:
    """Database cleanup service for managing event retention and storage optimization"""
    
    def __init__(self):
        self.retention_policies = {
            # High priority events - keep longer
            'high_priority': {
                'event_types': {'PushEvent', 'WorkflowRunEvent', 'DeleteEvent', 'MemberEvent', 'ReleaseEvent'},
                'retention_days': 90,
                'archive': True  # Move to archive table instead of delete
            },
            # Medium priority events 
            'medium_priority': {
                'event_types': {'PullRequestEvent', 'IssuesEvent', 'CreateEvent', 'ForkEvent'},
                'retention_days': 30,
                'archive': False
            },
            # Low priority events - keep minimal time
            'low_priority': {
                'event_types': {'WatchEvent', 'StarEvent'},
                'retention_days': 7,
                'archive': False
            }
        }
        
        # Anomaly detection records - keep longer for analysis
        self.anomaly_retention_days = 180
    
    async def run_cleanup(self, dry_run: bool = False) -> Dict[str, Any]:
        """Run complete database cleanup with optional dry run mode"""
        cleanup_stats = {
            'events_cleaned': 0,
            'events_archived': 0,
            'anomalies_cleaned': 0,
            'space_freed_estimate': 0,
            'dry_run': dry_run
        }
        
        db = SessionLocal()
        try:
            # Clean up events by priority
            for priority, policy in self.retention_policies.items():
                logger.info(f"Processing {priority} events cleanup...")
                stats = await self._cleanup_events_by_policy(db, policy, dry_run)
                cleanup_stats['events_cleaned'] += stats['deleted']
                cleanup_stats['events_archived'] += stats['archived']
                cleanup_stats['space_freed_estimate'] += stats['estimated_space_freed']
            
            # Clean up old anomaly detections
            logger.info("Processing anomaly detections cleanup...")
            anomaly_stats = await self._cleanup_anomaly_detections(db, dry_run)
            cleanup_stats['anomalies_cleaned'] = anomaly_stats['deleted']
            cleanup_stats['space_freed_estimate'] += anomaly_stats['estimated_space_freed']
            
            # Vacuum database if not dry run
            if not dry_run:
                await self._vacuum_database(db)
            
            if not dry_run:
                db.commit()
                logger.info(f"Cleanup completed: {cleanup_stats}")
            else:
                logger.info(f"Dry run completed: {cleanup_stats}")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            db.rollback()
            raise
        finally:
            db.close()
        
        return cleanup_stats
    
    async def _cleanup_events_by_policy(self, db: Session, policy: Dict[str, Any], dry_run: bool) -> Dict[str, int]:
        """Clean up events according to retention policy"""
        event_types = policy['event_types']
        retention_days = policy['retention_days']
        should_archive = policy['archive']
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        # Get count of events to be cleaned
        count_query = db.query(func.count(GitHubEvent.id)).filter(
            GitHubEvent.type.in_(event_types),
            GitHubEvent.created_at < cutoff_date
        )
        total_count = count_query.scalar() or 0
        
        if total_count == 0:
            logger.info(f"No {', '.join(event_types)} events older than {retention_days} days found")
            return {'deleted': 0, 'archived': 0, 'estimated_space_freed': 0}
        
        logger.info(f"Found {total_count} {', '.join(event_types)} events older than {retention_days} days")
        
        if dry_run:
            # Estimate space savings (rough calculation based on average row size)
            estimated_space = total_count * 2048  # Assume ~2KB per event on average
            return {
                'deleted': total_count if not should_archive else 0,
                'archived': total_count if should_archive else 0,
                'estimated_space_freed': estimated_space
            }
        
        archived_count = 0
        deleted_count = 0
        
        if should_archive:
            # Archive high-priority events instead of deleting them
            archived_count = await self._archive_events(db, event_types, cutoff_date)
        else:
            # Delete events in batches to avoid long-running transactions
            batch_size = 1000
            while True:
                events_to_delete = db.query(GitHubEvent).filter(
                    GitHubEvent.type.in_(event_types),
                    GitHubEvent.created_at < cutoff_date
                ).limit(batch_size).all()
                
                if not events_to_delete:
                    break
                
                for event in events_to_delete:
                    db.delete(event)
                
                deleted_count += len(events_to_delete)
                db.commit()  # Commit in batches
                
                logger.info(f"Deleted {deleted_count}/{total_count} events")
                
                if len(events_to_delete) < batch_size:
                    break
        
        estimated_space = total_count * 2048
        return {
            'deleted': deleted_count,
            'archived': archived_count,
            'estimated_space_freed': estimated_space
        }
    
    async def _archive_events(self, db: Session, event_types: set, cutoff_date: datetime) -> int:
        """Archive high-priority events to a separate table"""
        # Create archive table if it doesn't exist
        create_archive_sql = text("""
        CREATE TABLE IF NOT EXISTS github_events_archive (
            LIKE github_events INCLUDING ALL
        );
        """)
        db.execute(create_archive_sql)
        
        # Move events to archive table
        archive_sql = text("""
        INSERT INTO github_events_archive 
        SELECT * FROM github_events 
        WHERE type = ANY(:event_types) AND created_at < :cutoff_date;
        """)
        
        result = db.execute(archive_sql, {
            'event_types': list(event_types),
            'cutoff_date': cutoff_date
        })
        archived_count = result.rowcount
        
        # Delete original events after successful archive
        if archived_count > 0:
            delete_sql = text("""
            DELETE FROM github_events 
            WHERE type = ANY(:event_types) AND created_at < :cutoff_date;
            """)
            db.execute(delete_sql, {
                'event_types': list(event_types),
                'cutoff_date': cutoff_date
            })
        
        logger.info(f"Archived {archived_count} events")
        return archived_count
    
    async def _cleanup_anomaly_detections(self, db: Session, dry_run: bool) -> Dict[str, int]:
        """Clean up old anomaly detection records"""
        cutoff_date = datetime.utcnow() - timedelta(days=self.anomaly_retention_days)
        
        count_query = db.query(func.count(AnomalyDetection.id)).filter(
            AnomalyDetection.detection_timestamp < cutoff_date,
            AnomalyDetection.is_false_positive == True  # Only delete confirmed false positives
        )
        total_count = count_query.scalar() or 0
        
        if total_count == 0:
            logger.info(f"No anomaly detections older than {self.anomaly_retention_days} days found")
            return {'deleted': 0, 'estimated_space_freed': 0}
        
        logger.info(f"Found {total_count} old anomaly detections to clean up")
        
        if dry_run:
            estimated_space = total_count * 4096  # Anomaly records are larger
            return {'deleted': total_count, 'estimated_space_freed': estimated_space}
        
        # Delete in batches
        batch_size = 500
        deleted_count = 0
        
        while True:
            anomalies_to_delete = db.query(AnomalyDetection).filter(
                AnomalyDetection.detection_timestamp < cutoff_date,
                AnomalyDetection.is_false_positive == True
            ).limit(batch_size).all()
            
            if not anomalies_to_delete:
                break
            
            for anomaly in anomalies_to_delete:
                db.delete(anomaly)
            
            deleted_count += len(anomalies_to_delete)
            db.commit()  # Commit in batches
            
            logger.info(f"Deleted {deleted_count}/{total_count} anomaly detections")
            
            if len(anomalies_to_delete) < batch_size:
                break
        
        estimated_space = total_count * 4096
        return {'deleted': deleted_count, 'estimated_space_freed': estimated_space}
    
    async def _vacuum_database(self, db: Session):
        """Run VACUUM to reclaim disk space after deletions"""
        try:
            logger.info("Running database VACUUM to reclaim disk space...")
            # Note: VACUUM cannot be run inside a transaction
            db.commit()
            db.execute(text("VACUUM ANALYZE github_events;"))
            db.execute(text("VACUUM ANALYZE anomaly_detections;"))
            logger.info("Database VACUUM completed")
        except Exception as e:
            logger.warning(f"VACUUM failed (this is normal for some configurations): {e}")

    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get current database storage statistics"""
        db = SessionLocal()
        try:
            stats = {}
            
            # Get table sizes
            size_query = text("""
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                pg_total_relation_size(schemaname||'.'||tablename) as bytes
            FROM pg_tables 
            WHERE tablename IN ('github_events', 'anomaly_detections', 'github_events_archive')
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
            """)
            
            result = db.execute(size_query)
            for row in result:
                stats[row.tablename] = {
                    'size_pretty': row.size,
                    'size_bytes': row.bytes
                }
            
            # Get row counts
            for table in ['github_events', 'anomaly_detections']:
                count_query = text(f"SELECT COUNT(*) FROM {table};")
                count = db.execute(count_query).scalar()
                if table in stats:
                    stats[table]['row_count'] = count
                else:
                    stats[table] = {'row_count': count}
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {}
        finally:
            db.close()


# Cleanup task function for use with asyncio scheduler
async def run_daily_cleanup():
    """Daily cleanup task"""
    cleanup = DatabaseCleanup()
    try:
        await cleanup.run_cleanup(dry_run=False)
    except Exception as e:
        logger.error(f"Daily cleanup failed: {e}")


# CLI utility for manual cleanup
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Database cleanup utility')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be cleaned without making changes')
    parser.add_argument('--stats', action='store_true', help='Show storage statistics')
    
    args = parser.parse_args()
    
    cleanup = DatabaseCleanup()
    
    if args.stats:
        stats = asyncio.run(cleanup.get_storage_stats())
        print("Database Storage Statistics:")
        for table, data in stats.items():
            print(f"  {table}: {data}")
    else:
        print(f"Running cleanup (dry_run={args.dry_run})...")
        result = asyncio.run(cleanup.run_cleanup(dry_run=args.dry_run))
        print(f"Cleanup result: {result}")