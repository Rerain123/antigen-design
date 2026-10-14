from __future__ import annotations

import pytest

from t01_phase1_mock import AcceptanceHarness, FixtureRepository, SpecificationBundle


@pytest.fixture(scope="session")
def spec_bundle() -> SpecificationBundle:
    return SpecificationBundle.load()


@pytest.fixture(scope="session")
def fixture_repository(spec_bundle: SpecificationBundle) -> FixtureRepository:
    return FixtureRepository(spec_bundle)


@pytest.fixture(scope="session")
def m2_harness(
    spec_bundle: SpecificationBundle,
    fixture_repository: FixtureRepository,
) -> AcceptanceHarness:
    return AcceptanceHarness(bundle=spec_bundle, fixtures=fixture_repository)


@pytest.fixture(scope="session")
def case_executions(m2_harness: AcceptanceHarness):
    return m2_harness.execute_cases()


@pytest.fixture(scope="session")
def execution_by_key(case_executions):
    return {item.scenario["scenario_key"]: item for item in case_executions}


@pytest.fixture(scope="session")
def m2_report(m2_harness: AcceptanceHarness, case_executions):
    return m2_harness.run(case_executions)
