from unittest.mock import Mock

from botocore.exceptions import ClientError

from app.common import metrics


def test_publish_metric_formats_dimensions(monkeypatch) -> None:
    client = Mock()
    monkeypatch.setattr(metrics, "_client", lambda: client)

    metrics.publish_metric(
        "WorkerExecutionTime",
        1.25,
        unit="Seconds",
        dimensions={"Worker": "news"},
    )

    client.put_metric_data.assert_called_once_with(
        Namespace="FinanceDev/Ingestion",
        MetricData=[{
            "MetricName": "WorkerExecutionTime",
            "Value": 1.25,
            "Unit": "Seconds",
            "Dimensions": [{"Name": "Worker", "Value": "news"}],
        }],
    )


def test_publish_metric_does_not_fail_ingestion(monkeypatch) -> None:
    client = Mock()
    client.put_metric_data.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "denied"}},
        "PutMetricData",
    )
    monkeypatch.setattr(metrics, "_client", lambda: client)

    metrics.publish_news_articles(5)
