"""Unit tests for IdeaDeduplicationService, title/topic normalization, and angle differentiation."""

from vasukisquare.research.deduplication import (
    IdeaDeduplicationService,
    normalize_title,
    normalize_topic,
)


def test_normalize_title_and_topic():
    title1 = "The Complete Guide to Modern PostgreSQL for Beginners!"
    assert normalize_title(title1) == "postgresql"

    title2 = "Mastering Kubernetes: A Deep Dive into Distributed Pod Scheduling"
    assert normalize_title(title2) == "kubernetes distributed pod scheduling"

    topic = "Getting Started with Python Asyncio"
    assert normalize_topic(topic) == "python asyncio"


def test_dedup_exact_normalized_title_match():
    service = IdeaDeduplicationService()
    historical = [
        {
            "id": "book-1",
            "title": "Kafka Architecture and Event Streams",
            "topic": "Kafka Architecture",
            "summary": "Distributed event streaming with Apache Kafka",
            "angle": "Core internal architecture and replication",
        }
    ]

    # Candidate with same core title words
    match = service.check_duplicate(
        candidate_title="The Complete Kafka Architecture and Event Streams",
        candidate_topic="Kafka Internals",
        candidate_summary="A guide to Kafka architecture",
        candidate_angle="Core internal architecture and replication",
        historical_records=historical,
    )
    assert match.is_duplicate is True
    assert "Duplicate title" in (match.reason or "")
    assert match.matched_record_id == "book-1"


def test_dedup_exact_normalized_topic_match():
    service = IdeaDeduplicationService()
    historical = [
        {
            "id": "book-2",
            "title": "PostgreSQL Internals",
            "topic": "PostgreSQL Database Engine",
            "summary": "Storage engines and WAL in Postgres",
            "angle": "WAL, buffer pools, and vacuum mechanics",
        }
    ]

    match = service.check_duplicate(
        candidate_title="Under the Hood of Postgres",
        candidate_topic="PostgreSQL Database Engine",
        candidate_summary="Storage engine architecture",
        candidate_angle="WAL buffer pools vacuum mechanics",
        historical_records=historical,
    )
    assert match.is_duplicate is True
    assert "Same core topic" in (match.reason or "")


def test_dedup_high_token_overlap_rejection():
    service = IdeaDeduplicationService()
    historical = [
        {
            "id": "book-3",
            "title": "Microservices with Go and gRPC",
            "topic": "Building microservices using Golang and gRPC protobufs",
            "summary": "Practical service communication, protocol buffers, interceptors, and load balancing",
            "angle": "Service communication with gRPC",
        }
    ]

    # Minor rewording
    match = service.check_duplicate(
        candidate_title="Golang Microservices using gRPC",
        candidate_topic="Building microservices with Go and gRPC protobufs",
        candidate_summary="Practical service communication with protocol buffers, interceptors, and balancing",
        candidate_angle="Service communication with gRPC",
        historical_records=historical,
    )
    assert match.is_duplicate is True
    assert match.similarity_score >= 0.70


def test_dedup_genuinely_different_angle_accepted():
    service = IdeaDeduplicationService()
    historical = [
        {
            "id": "book-4",
            "title": "PostgreSQL Query Optimization",
            "topic": "PostgreSQL Database Performance",
            "summary": "Index tuning, explain analyze plans, and SQL query optimization techniques",
            "angle": "SQL query profiling, composite indexes, and query planner optimization",
        }
    ]

    # Different angle on the same topic: DevOps, High Availability & Disaster Recovery
    match = service.check_duplicate(
        candidate_title="PostgreSQL High Availability and Disaster Recovery",
        candidate_topic="PostgreSQL Database Performance",
        candidate_summary="Patroni clusters, synchronous replication, WAL archiving, and automated failover runbooks",
        candidate_angle="High availability clustering with Patroni, etcd quorum, physical replication, and multi-region failover runbooks",
        historical_records=historical,
    )
    assert match.is_duplicate is False
    assert match.distinct_angle_accepted is True


def test_dedup_prompt_example_beginner_python_duplicate():
    """Existing 'Python for Beginners' should reject candidate 'Beginner Python Programming'."""
    service = IdeaDeduplicationService()
    historical = [
        {
            "id": "book-py-1",
            "title": "Python for Beginners",
            "topic": "Python Programming",
            "summary": "Introductory guide to Python programming basics, syntax, variables, and loops.",
            "angle": "Beginner fundamentals, language syntax, basic data structures",
        }
    ]

    match = service.check_duplicate(
        candidate_title="Beginner Python Programming",
        candidate_topic="Python Programming",
        candidate_summary="Learn Python from scratch with basic variables, loops, functions, and syntax.",
        candidate_angle="Beginner fundamentals and language basics",
        historical_records=historical,
    )
    assert match.is_duplicate is True


def test_dedup_prompt_example_async_python_distinct_allowed():
    """Existing 'Python for Beginners' should allow candidate 'High-Performance Async Python Services'."""
    service = IdeaDeduplicationService()
    historical = [
        {
            "id": "book-py-1",
            "title": "Python for Beginners",
            "topic": "Python Programming",
            "summary": "Introductory guide to Python programming basics, syntax, variables, and loops.",
            "angle": "Beginner fundamentals, language syntax, basic data structures",
        }
    ]

    match = service.check_duplicate(
        candidate_title="High-Performance Async Python Services",
        candidate_topic="Async Python Backend Services",
        candidate_summary="Production async architecture with asyncio event loop, uvloop, FastAPI, multiprocessing workers, and connection pooling.",
        candidate_angle="Advanced concurrency, uvloop internals, non-blocking I/O benchmarks, and distributed worker architectures",
        historical_records=historical,
    )
    assert match.is_duplicate is False

