from collections.abc import Mapping
from functools import lru_cache

import boto3
import structlog
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings

NAMESPACE = "FinanceDev/Ingestion"
log = structlog.get_logger()


@lru_cache(maxsize=1)
def _client():
    return boto3.client("cloudwatch", region_name=get_settings().aws_region)


def publish_metric(
    name: str,
    value: float,
    *,
    unit: str = "Count",
    dimensions: Mapping[str, str] | None = None,
) -> None:
    """Publish one ingestion metric without making monitoring a job dependency."""
    metric = {
        "MetricName": name,
        "Value": value,
        "Unit": unit,
        "Dimensions": [
            {"Name": key, "Value": dimension_value}
            for key, dimension_value in sorted((dimensions or {}).items())
        ],
    }
    try:
        _client().put_metric_data(Namespace=NAMESPACE, MetricData=[metric])
    except (BotoCoreError, ClientError) as exc:
        log.warning("cloudwatch_metric_publish_failed", metric=name, error=str(exc))


def publish_stock_ingest_age(age_seconds: float) -> None:
    publish_metric("StockIngestAgeSeconds", age_seconds, unit="Seconds")


def publish_options_rows(rows: int) -> None:
    publish_metric("OptionsRowsIngested", rows, unit="Count")


def publish_news_articles(articles: int) -> None:
    publish_metric("NewsArticlesIngested", articles, unit="Count")


def publish_api_failure(*, provider: str | None = None) -> None:
    dimensions = {"Provider": provider} if provider else None
    publish_metric("APIFailures", 1, dimensions=dimensions)


def publish_ingestion_error(*, worker: str) -> None:
    publish_metric("IngestionErrors", 1, dimensions={"Worker": worker})


def publish_worker_execution_time(*, worker: str, seconds: float) -> None:
    publish_metric(
        "WorkerExecutionTime",
        seconds,
        unit="Seconds",
        dimensions={"Worker": worker},
    )
