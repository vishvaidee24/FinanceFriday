import gzip
import json
from datetime import datetime, timezone
from typing import Any
import boto3
from app.config import get_settings

class RawArchive:
    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.raw_bucket_name
        self.client = boto3.client("s3", region_name=settings.aws_region)

    def put_json(
        self,
        *,
        provider: str,
        dataset: str,
        object_name: str,
        payload: Any,
        observed_at: datetime | None = None,
    ) -> str:
        observed_at = observed_at or datetime.now(timezone.utc)
        key = (
            f"raw/{provider}/{dataset}/"
            f"year={observed_at:%Y}/month={observed_at:%m}/day={observed_at:%d}/"
            f"{object_name}.json.gz"
        )
        body = gzip.compress(json.dumps(payload, default=str).encode("utf-8"))
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
            ContentEncoding="gzip",
        )
        return key
