import argparse
import json
import os
from uuid import uuid4

import httpx


def build_payload(text: str, request_id: str) -> dict[str, str]:
    return {"text": text, "client_request_id": request_id}


def main() -> None:
    parser = argparse.ArgumentParser(description="Call the WarmAI task-analysis API")
    parser.add_argument("text")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default=os.getenv("WARMAI_API_KEY"))
    args = parser.parse_args()
    if not args.api_key:
        parser.error("--api-key or WARMAI_API_KEY is required")

    request_id = str(uuid4())
    response = httpx.post(
        f"{args.base_url.rstrip('/')}/v1/task-analysis",
        headers={
            "X-API-Key": args.api_key,
            "Idempotency-Key": request_id,
        },
        json=build_payload(args.text, request_id),
        timeout=5.0,
    )
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))
    raise SystemExit(0 if response.is_success else 1)


if __name__ == "__main__":
    main()
