"""
Metrics and Observability Service.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Union
from sqlalchemy.orm import Session
from src.models.system_metric import SystemMetric

logger = logging.getLogger("eip.metrics_service")

class MetricsService:
    """
    Service to record, query, and aggregate system operational metrics.
    """
    VALID_METRICS = {
        "feeds_processed",
        "feeds_succeeded",
        "feeds_failed",
        "articles_fetched",
        "articles_rejected",
        "articles_stored",
        "events_created",
        "events_merged",
        "breaking_alerts_sent",
        "digests_sent",
        "telegram_failures",
        "scheduler_failures",
        "average_digest_size",
        "processing_time_ms",
        "dead_feeds_detected",
        "system_heartbeat",
        "memory_usage_mb",
        "database_size_mb",
        "active_feeds",
        "scheduler_running"
    }

    METRIC_DEFAULTS = {
        "feeds_processed": {"aggregation_type": "COUNTER", "source": "CollectionService"},
        "feeds_succeeded": {"aggregation_type": "COUNTER", "source": "CollectionService"},
        "feeds_failed": {"aggregation_type": "COUNTER", "source": "CollectionService"},
        "articles_fetched": {"aggregation_type": "COUNTER", "source": "CollectionService"},
        "articles_rejected": {"aggregation_type": "COUNTER", "source": "CollectionService"},
        "articles_stored": {"aggregation_type": "COUNTER", "source": "CollectionService"},
        "events_created": {"aggregation_type": "COUNTER", "source": "EventService"},
        "events_merged": {"aggregation_type": "COUNTER", "source": "EventService"},
        "breaking_alerts_sent": {"aggregation_type": "COUNTER", "source": "SchedulerService"},
        "digests_sent": {"aggregation_type": "COUNTER", "source": "SchedulerService"},
        "telegram_failures": {"aggregation_type": "COUNTER", "source": "TelegramService"},
        "scheduler_failures": {"aggregation_type": "COUNTER", "source": "SchedulerService"},
        "average_digest_size": {"aggregation_type": "AVERAGE", "source": "DigestService"},
        "processing_time_ms": {"aggregation_type": "TIMER", "source": "SchedulerService"},
        "dead_feeds_detected": {"aggregation_type": "COUNTER", "source": "CollectionService"},
        "system_heartbeat": {"aggregation_type": "COUNTER", "source": "SchedulerService"},
        "memory_usage_mb": {"aggregation_type": "GAUGE", "source": "SchedulerService"},
        "database_size_mb": {"aggregation_type": "GAUGE", "source": "SchedulerService"},
        "active_feeds": {"aggregation_type": "GAUGE", "source": "SchedulerService"},
        "scheduler_running": {"aggregation_type": "GAUGE", "source": "SchedulerService"},
    }

    def record_metric(
        self,
        session: Session,
        metric_name: str,
        metric_value: Union[int, float],
        aggregation_type: Optional[str] = None,
        source: Optional[str] = None,
        metadata: Optional[dict] = None,
        created_at: Optional[datetime] = None
    ) -> SystemMetric:
        """
        Creates and persists a system metric record.
        """
        if metric_name not in self.VALID_METRICS:
            raise ValueError(f"Invalid metric name: {metric_name}")

        defaults = self.METRIC_DEFAULTS.get(metric_name, {})
        agg_type = aggregation_type or defaults.get("aggregation_type", "COUNTER")
        src_val = source or defaults.get("source", "System")

        # Validation for aggregation_type values
        if agg_type not in {"COUNTER", "GAUGE", "AVERAGE", "TIMER"}:
            raise ValueError(f"Invalid aggregation type: {agg_type}")

        meta = metadata or {}
        created_val = created_at or datetime.now(timezone.utc)
        metric = SystemMetric(
            metric_name=metric_name,
            metric_value=float(metric_value),
            aggregation_type=agg_type,
            source=src_val,
            metadata_json=meta,
            created_at=created_val
        )
        session.add(metric)
        session.flush()
        logger.info(f"Recorded metric: {metric_name} ({agg_type}) from {src_val} = {metric_value}")
        return metric

    def increment(
        self,
        session: Session,
        metric_name: str,
        amount: int = 1,
        source: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> SystemMetric:
        """
        Increments a count-based metric by recording a value.
        """
        defaults = self.METRIC_DEFAULTS.get(metric_name, {})
        agg_type = defaults.get("aggregation_type", "COUNTER")
        src_val = source or defaults.get("source", "System")
        return self.record_metric(
            session=session,
            metric_name=metric_name,
            metric_value=amount,
            aggregation_type=agg_type,
            source=src_val,
            metadata=metadata
        )

    def get_metric(
        self,
        session: Session,
        metric_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        source: Optional[str] = None
    ) -> List[SystemMetric]:
        """
        Queries and filters system metrics.
        """
        if metric_name not in self.VALID_METRICS:
            raise ValueError(f"Invalid metric name: {metric_name}")

        query = session.query(SystemMetric).filter(
            SystemMetric.metric_name == metric_name
        )

        if start_date is not None:
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=timezone.utc)
            query = query.filter(SystemMetric.created_at >= start_date)

        if end_date is not None:
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
            query = query.filter(SystemMetric.created_at <= end_date)

        if source is not None:
            query = query.filter(SystemMetric.source == source)

        return query.order_by(SystemMetric.created_at.asc()).all()

    def daily_metrics_summary(
        self,
        session: Session
    ) -> dict:
        """
        Computes aggregates for all metrics in the last 24 hours.
        Rules:
        - COUNTER: SUM (default 0)
        - GAUGE: LATEST VALUE (default 0.0)
        - AVERAGE: AVG (default 0.0)
        - TIMER: AVG + MAX (default 0.0 for avg/max)
        """
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        metrics = session.query(SystemMetric).filter(
            SystemMetric.created_at >= cutoff
        ).all()

        # Group metrics by name
        grouped = {name: [] for name in self.VALID_METRICS}
        for m in metrics:
            if m.metric_name in grouped:
                grouped[m.metric_name].append(m)

        summary = {}
        for name in self.VALID_METRICS:
            defaults = self.METRIC_DEFAULTS.get(name, {})
            records = grouped[name]
            agg_type = records[0].aggregation_type if records else defaults.get("aggregation_type", "COUNTER")

            if name == "processing_time_ms":
                # TIMER: returns AVG and MAX as separate keys
                if records:
                    values = [r.metric_value for r in records]
                    summary["processing_time_ms_avg"] = float(sum(values) / len(values))
                    summary["processing_time_ms_max"] = float(max(values))
                else:
                    summary["processing_time_ms_avg"] = 0.0
                    summary["processing_time_ms_max"] = 0.0
            elif agg_type == "COUNTER":
                summary[name] = int(sum(r.metric_value for r in records)) if records else 0
            elif agg_type == "AVERAGE":
                summary[name] = float(sum(r.metric_value for r in records) / len(records)) if records else 0.0
            elif agg_type == "GAUGE":
                if records:
                    # Sort by created_at (handling timezone-aware datetimes)
                    latest_rec = max(records, key=lambda r: r.created_at)
                    summary[name] = float(latest_rec.metric_value)
                else:
                    summary[name] = 0.0
            else:
                # Fallback
                summary[name] = float(sum(r.metric_value for r in records) / len(records)) if records else 0.0

        logger.info("Generated daily metrics summary.")
        return summary
