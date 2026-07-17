"""Shared pytest fixtures."""

import pytest
from opentelemetry import metrics as otel_metrics
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased

# The OTel API only allows a global TracerProvider/MeterProvider to be
# registered ONCE per process — a second `set_tracer_provider`/
# `set_meter_provider` call is a silent no-op with a warning. So rather than
# each test installing its own provider, one shared in-memory exporter/
# reader pair is registered here at collection time, and tests read from
# (and, for spans, clear) the shared instance via the fixtures below.
#
# sampler is explicit (always-on) so span-count assertions never depend on
# the ambient process environment: TracerProvider() with no sampler= falls
# back to reading OTEL_TRACES_SAMPLER/OTEL_TRACES_SAMPLER_ARG from the real
# environment, and .env.example now ships uncommented
# OTEL_TRACES_SAMPLER_ARG=0.25 recommendations that would otherwise make
# these tests flake if ever sourced into the shell (see R3-002).
_span_exporter = InMemorySpanExporter()
_tracer_provider = TracerProvider(sampler=ParentBased(ALWAYS_ON))
_tracer_provider.add_span_processor(SimpleSpanProcessor(_span_exporter))
otel_trace.set_tracer_provider(_tracer_provider)

_metric_reader = InMemoryMetricReader()
_meter_provider = MeterProvider(metric_readers=[_metric_reader])
otel_metrics.set_meter_provider(_meter_provider)


@pytest.fixture
def otel_span_exporter() -> InMemorySpanExporter:
    """Shared in-memory span exporter, cleared before each test that uses it."""
    _span_exporter.clear()
    return _span_exporter


@pytest.fixture
def otel_metric_reader() -> InMemoryMetricReader:
    """
    Shared in-memory metric reader.

    Counters are cumulative and shared across the whole test session (the
    global MeterProvider can only be registered once — see above), so tests
    must diff a specific attribute set's value before/after acting rather
    than asserting an absolute total.
    """
    return _metric_reader
