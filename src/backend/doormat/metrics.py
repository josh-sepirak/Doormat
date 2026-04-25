"""Metrics collection and exposure for Prometheus."""

from prometheus_client import Counter, Gauge, Histogram

# API request metrics
http_requests_total = Counter(
    "doormat_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
http_request_duration_seconds = Histogram(
    "doormat_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)

# Cost tracking metrics
llm_calls_total = Counter(
    "doormat_llm_calls_total",
    "Total LLM API calls",
    ["service", "model", "status"],
)
llm_tokens_total = Counter(
    "doormat_llm_tokens_total",
    "Total tokens consumed",
    ["service", "model", "type"],  # type = prompt/completion
)
llm_cost_usd_total = Counter(
    "doormat_llm_cost_usd_total",
    "Total cost in USD",
    ["service", "model"],
)
llm_request_duration_seconds = Histogram(
    "doormat_llm_request_duration_seconds",
    "LLM request latency",
    ["service", "model"],
)

# Current state gauges
active_requests = Gauge(
    "doormat_active_requests",
    "Currently active HTTP requests",
)
current_cost_usd = Gauge(
    "doormat_current_cost_usd",
    "Total cost accumulated (session)",
)


def record_http_request(
    method: str, endpoint: str, status: int, duration_ms: float
) -> None:
    """Record HTTP request metrics."""
    http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
    http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(
        duration_ms / 1000
    )


def record_llm_call(
    service: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    duration_ms: float,
    status: str = "success",
) -> None:
    """Record LLM API call metrics."""
    llm_calls_total.labels(service=service, model=model, status=status).inc()
    llm_tokens_total.labels(service=service, model=model, type="prompt").inc(
        prompt_tokens
    )
    llm_tokens_total.labels(service=service, model=model, type="completion").inc(
        completion_tokens
    )
    llm_cost_usd_total.labels(service=service, model=model).inc(cost_usd)
    llm_request_duration_seconds.labels(service=service, model=model).observe(
        duration_ms / 1000
    )


def update_cost_gauge(cost_usd: float) -> None:
    """Update current cost gauge."""
    current_cost_usd.set(cost_usd)


def increment_active_requests() -> None:
    """Increment active requests counter."""
    active_requests.inc()


def decrement_active_requests() -> None:
    """Decrement active requests counter."""
    active_requests.dec()
