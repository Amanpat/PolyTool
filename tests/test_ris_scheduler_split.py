"""Tests for scheduler job-exclusion (CPU/GPU service split).

Validates that start_research_scheduler(exclude_job_ids=[...]) skips the
specified jobs and only registers the rest.
"""
from __future__ import annotations

import pytest


class FakeScheduler:
    def __init__(self):
        self.jobs: list[str] = []
        self.started = False

    def add_job(self, fn, trigger, id: str, name: str):
        self.jobs.append(id)

    def start(self):
        self.started = True


def _start(exclude=None):
    from packages.research.scheduling.scheduler import start_research_scheduler, JOB_REGISTRY

    recorded: list[str] = []

    def fake_factory():
        return FakeScheduler()

    # We want to capture which job ids were registered, so use _job_runner.
    def runner(job_id: str) -> None:
        pass

    sched = start_research_scheduler(
        _scheduler_factory=fake_factory,
        _job_runner=runner,
        exclude_job_ids=exclude,
    )
    return sched


class TestSchedulerExcludeJobs:
    def test_no_exclusion_registers_all_jobs(self):
        from packages.research.scheduling.scheduler import JOB_REGISTRY

        sched = _start(exclude=None)
        assert set(sched.jobs) == {j["id"] for j in JOB_REGISTRY}

    def test_exclude_academic_ingest(self):
        """CPU scheduler: academic_ingest excluded, all other jobs present."""
        from packages.research.scheduling.scheduler import JOB_REGISTRY

        sched = _start(exclude=["academic_ingest"])
        assert "academic_ingest" not in sched.jobs
        # Every other job is still registered
        other_ids = {j["id"] for j in JOB_REGISTRY if j["id"] != "academic_ingest"}
        assert other_ids.issubset(set(sched.jobs))

    def test_exclude_multiple_jobs(self):
        sched = _start(exclude=["academic_ingest", "weekly_digest"])
        assert "academic_ingest" not in sched.jobs
        assert "weekly_digest" not in sched.jobs

    def test_exclude_empty_list_registers_all(self):
        from packages.research.scheduling.scheduler import JOB_REGISTRY

        sched = _start(exclude=[])
        assert set(sched.jobs) == {j["id"] for j in JOB_REGISTRY}

    def test_scheduler_started(self):
        sched = _start(exclude=["academic_ingest"])
        assert sched.started
