from datetime import datetime, timezone
from typing import Any, Dict

def wrap_data(data: Any, source: str = "live", last_updated: datetime = None) -> Dict[str, Any]:
    """Standardize the API response format with a metadata envelope."""
    return {
        "status": "success",
        "data": data,
        "metadata": {
            "data_source": source, # 'live', 'cached', 'demo'
            "last_updated": (last_updated or datetime.now(timezone.utc)).isoformat(),
            "api_version": "1.0.0",
            "environment": "development" # Should be env-driven in prod
        }
    }
