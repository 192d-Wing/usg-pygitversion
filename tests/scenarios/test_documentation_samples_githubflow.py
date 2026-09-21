# SPDX-License-Identifier: MIT
"""Port of upstream ``DocumentationSamplesForGitHubFlow.cs`` (6.8.2), non-Mainline cases."""

from __future__ import annotations

import pytest

from tests.scenarios.dsl import Scenario, githubflow

pytestmark = pytest.mark.scenario


@pytest.mark.parametrize("with_pull_request", [False, True])
def test_feature_branch(with_pull_request: bool) -> None:
    configuration = githubflow()
    with Scenario() as f:
        f.make_a_commit()
        f.apply_tag("1.2.0")
        f.assert_full_semver("1.2.0", configuration)
        f.branch_to("feature/foo")
        f.assert_full_semver("1.2.1-foo.1+0", configuration)
        f.make_a_commit()
        f.assert_full_semver("1.2.1-foo.1+1", configuration)
        f.checkout("main")
        f.make_a_commit()
        f.assert_full_semver("1.2.1-1", configuration)
        f.apply_tag("1.2.1")
        f.assert_full_semver("1.2.1", configuration)
        f.merge_to("feature/foo")
        f.assert_full_semver("1.2.2-foo.1+2", configuration)
        f.make_a_commit("+semver: minor")
        f.assert_full_semver("1.3.0-foo.1+3", configuration)
        f.apply_tag("2.0.0-foo.1")
        f.assert_full_semver("2.0.0-foo.2+0", configuration)
        f.make_a_commit()
        f.assert_full_semver("2.0.0-foo.2+1", configuration)
        f.checkout("main")
        if with_pull_request:
            f.branch_to("pull/2/merge")
            f.merge_no_ff("feature/foo")
            f.assert_full_semver("2.0.0-PullRequest2.5", configuration)
            f.checkout("main")
            f.delete_branch("pull/2/merge")
        f.merge_no_ff("feature/foo")
        f.delete_branch("feature/foo")
        f.assert_full_semver("2.0.0-5", configuration)
        f.make_a_commit()
        f.assert_full_semver("2.0.0-6", configuration)
        f.apply_tag("2.0.0")
        f.assert_full_semver("2.0.0", configuration)


@pytest.mark.parametrize("with_pull_request", [False, True])
def test_release_branch(with_pull_request: bool) -> None:
    configuration = githubflow()
    with Scenario() as f:
        f.make_a_commit()
        f.apply_tag("1.2.0")
        f.assert_full_semver("1.2.0", configuration)
        f.branch_to("release/next")
        f.assert_full_semver("1.2.1-beta.1+0", configuration)
        f.make_a_commit()
        f.assert_full_semver("1.2.1-beta.1+1", configuration)
        f.checkout("main")
        f.make_a_commit()
        f.assert_full_semver("1.2.1-1", configuration)
        f.apply_tag("1.2.1")
        f.assert_full_semver("1.2.1", configuration)
        f.merge_to("release/next")
        f.assert_full_semver("1.2.2-beta.1+2", configuration)
        f.make_a_commit("+semver: minor")
        f.assert_full_semver("1.3.0-beta.1+3", configuration)
        f.apply_tag("1.3.1-beta.1")
        f.assert_full_semver("1.3.1-beta.2+0", configuration)
        f.make_a_commit()
        f.assert_full_semver("1.3.1-beta.2+1", configuration)
        f.checkout("main")
        if with_pull_request:
            f.branch_to("pull/2/merge")
            f.merge_no_ff("release/next")
            f.assert_full_semver("1.3.1-PullRequest2.5", configuration)
            f.checkout("main")
            f.delete_branch("pull/2/merge")
        f.merge_no_ff("release/next")
        f.delete_branch("release/next")
        f.assert_full_semver("1.3.1-5", configuration)
        f.make_a_commit()
        f.assert_full_semver("1.3.1-6", configuration)
        f.apply_tag("1.3.1")
        f.assert_full_semver("1.3.1", configuration)


@pytest.mark.parametrize("with_pull_request", [False, True])
def test_versioned_release_branch(with_pull_request: bool) -> None:
    configuration = githubflow()
    with Scenario() as f:
        f.make_a_commit()
        f.apply_tag("1.2.0")
        f.assert_full_semver("1.2.0", configuration)
        f.branch_to("release/2.2.1")
        f.assert_full_semver("2.2.1-beta.1+0", configuration)
        f.make_a_commit()
        f.assert_full_semver("2.2.1-beta.1+1", configuration)
        f.checkout("main")
        f.make_a_commit()
        f.assert_full_semver("1.2.1-1", configuration)
        f.apply_tag("2.2.1")
        f.assert_full_semver("2.2.1", configuration)
        f.merge_to("release/2.2.1")
        f.assert_full_semver("2.2.2-beta.1+2", configuration)
        f.make_a_commit("+semver: minor")
        f.assert_full_semver("2.3.0-beta.1+3", configuration)
        f.apply_tag("2.3.1-beta.1")
        f.assert_full_semver("2.3.1-beta.2+0", configuration)
        f.make_a_commit()
        f.assert_full_semver("2.3.1-beta.2+1", configuration)
        f.checkout("main")
        if with_pull_request:
            f.branch_to("pull/2/merge")
            f.merge_no_ff("release/2.2.1")
            f.assert_full_semver("2.3.1-PullRequest2.5", configuration)
            f.checkout("main")
            f.delete_branch("pull/2/merge")
        f.merge_no_ff("release/2.2.1")
        f.delete_branch("release/2.2.1")
        f.assert_full_semver("2.3.1-5", configuration)
        f.make_a_commit()
        f.assert_full_semver("2.3.1-6", configuration)
        f.apply_tag("2.3.1")
        f.assert_full_semver("2.3.1", configuration)


@pytest.mark.skip(reason="Mainline variants land in Phase 4")
def test_mainline_variants() -> None:
    pass
