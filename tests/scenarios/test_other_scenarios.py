# SPDX-License-Identifier: MIT
"""Port of upstream ``IntegrationTests/OtherScenarios.cs`` (6.8.2)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.scenarios.dsl import GitFlowScenario, RemoteScenario, Scenario, gitflow, githubflow

pytestmark = pytest.mark.scenario


def test_do_not_blow_up_when_main_and_develop_point_at_same_commit() -> None:
    with RemoteScenario() as f:
        f.make_a_commit()
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit()
        f.create_branch("develop")
        f.local.fetch()
        f.local.checkout(f.head_sha)
        f.local.delete_branch("main")
        f.assert_full_semver("1.0.1-1")


def test_allow_not_having_main() -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit()
        f.branch_to("develop")
        f.delete_branch("main")
        f.assert_full_semver("1.1.0-alpha.1")


@pytest.mark.parametrize("branch", ["masterfix", "mainfix"])
def test_allow_having_variants_starting_with_main_or_master(branch: str) -> None:
    with Scenario() as f:
        f.make_a_commit()
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit()
        f.branch_to(branch)
        f.assert_full_semver(f"1.0.1-{branch}.1+1")


def test_allow_having_master_instead_of_main() -> None:
    with Scenario() as f:
        f.make_a_commit("one")
        f.branch_to("develop")
        f.branch_to("master")
        f.delete_branch("main")
        f.assert_full_semver("0.0.1-1")


@pytest.mark.parametrize(("stage", "count"), [(True, 1), (False, 1), (True, 5), (False, 5)])
def test_has_dirty_flag_when_uncommitted_changes_are_in_repository(stage: bool, count: int) -> None:
    with Scenario() as f:
        f.make_a_commit()
        for i in range(count):
            path = f.path / f"dirty{i}.txt"
            path.write_text(f"Hello world / testfile {i}", encoding="utf-8")
            if stage:
                f.git("add", "--", path.name)
        assert f.get_version()["UncommittedChanges"] == str(count)


def test_no_dirty_flag_in_clean_repository() -> None:
    with Scenario() as f:
        f.make_a_commit()
        assert f.get_version()["UncommittedChanges"] == "0"


@pytest.mark.parametrize(("track", "expected"), [(False, "1.1.0-alpha.2"), (True, "1.2.0-alpha.1")])
def test_ensure_track_merge_target_strategy_which_will_look_for_tagged_merge_commits(
    track: bool, expected: str
) -> None:
    c = gitflow(
        branches={
            "main": {"is_main_branch": False},
            "develop": {"track_merge_target": track, "tracks_release_branches": False},
        }
    )
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("develop")
        f.make_a_commit()
        f.checkout("main")
        f.merge_no_ff("develop")
        f.apply_tag("1.1.0")
        f.checkout("develop")
        f.make_a_commit()
        f.assert_full_semver(expected, c)


def test_ensure_pre_release_tag_label_will_be_considered_if_current_branch_is_release() -> None:
    c = githubflow()
    with Scenario("release/2.0.0") as f:
        f.make_a_commit()
        f.assert_full_semver("2.0.0-beta.1+1", c)
        f.apply_tag("2.0.0-beta.1")
        f.assert_full_semver("2.0.0-beta.2+0", c)
        f.make_a_commit()
        f.assert_full_semver("2.0.0-beta.2+1", c)


# The twelve "EnsurePreReleaseTagLabel..." tests share one shape: an optional
# initial 1.0.0 tag, a patch number, a label configuration, and a sequence of
# expectations. Each row is (label config, initial tag, expected sequence),
# where "{p}" is the patch number and "{q}" is patch + 1.
_LABEL_SEQUENCES: list[tuple[dict[str, Any], bool, list[str]]] = [
    # No label at all.
    (
        {"label": None, "branches": {"main": {"label": None}}},
        False,
        ["0.0.1-1+1", "0.0.{p}-alpha.1", "0.0.{p}-alpha.2+1", "0.0.{p}-alpha.2+2", "0.0.{p}-beta.1",
         "0.0.{p}-beta.2+1", "0.0.{p}-beta.2", "0.0.{p}-beta.3+1", "0.0.{p}", "0.0.{q}-1+1"],
    ),
    (
        {"label": None, "branches": {"main": {"label": None}}},
        True,
        ["1.0.1-1+1", "1.0.{p}-alpha.1", "1.0.{p}-alpha.2+1", "1.0.{p}-alpha.2+2", "1.0.{p}-beta.1",
         "1.0.{p}-beta.2+1", "1.0.{p}-beta.2", "1.0.{p}-beta.3+1", "1.0.{p}", "1.0.{q}-1+1"],
    ),
    # Empty label.
    (
        {"branches": {"main": {"label": ""}}},
        False,
        ["0.0.1-1+1", "0.0.{p}-1+1", "0.0.{p}-1+2", "0.0.{p}-1+3", "0.0.{p}-1+4",
         "0.0.{p}-1+5", "0.0.{p}-1+6", "0.0.{p}-1+7", "0.0.{p}", "0.0.{q}-1+1"],
    ),
    (
        {"branches": {"main": {"label": ""}}},
        True,
        ["1.0.1-1+1", "1.0.{p}-1+1", "1.0.{p}-1+2", "1.0.{p}-1+3", "1.0.{p}-1+4",
         "1.0.{p}-1+5", "1.0.{p}-1+6", "1.0.{p}-1+7", "1.0.{p}", "1.0.{q}-1+1"],
    ),
    # alpha label.
    (
        {"label": None, "branches": {"main": {"label": "alpha"}}},
        False,
        ["0.0.1-alpha.1+1", "0.0.{p}-alpha.1", "0.0.{p}-alpha.2+1", "0.0.{p}-alpha.2+2", "0.0.{p}-alpha.2+3",
         "0.0.{p}-alpha.2+4", "0.0.{p}-alpha.2+5", "0.0.{p}-alpha.2+6", "0.0.{p}", "0.0.{q}-alpha.1+1"],
    ),
    (
        {"label": None, "branches": {"main": {"label": "alpha"}}},
        True,
        ["1.0.1-alpha.1+1", "1.0.{p}-alpha.1", "1.0.{p}-alpha.2+1", "1.0.{p}-alpha.2+2", "1.0.{p}-alpha.2+3",
         "1.0.{p}-alpha.2+4", "1.0.{p}-alpha.2+5", "1.0.{p}-alpha.2+6", "1.0.{p}", "1.0.{q}-alpha.1+1"],
    ),
    # beta label.
    (
        {"branches": {"main": {"label": "beta"}}},
        False,
        ["0.0.1-beta.1+1", "0.0.{p}-beta.1+1", "0.0.{p}-beta.1+2", "0.0.{p}-beta.1+3", "0.0.{p}-beta.1",
         "0.0.{p}-beta.2+1", "0.0.{p}-beta.2", "0.0.{p}-beta.3+1", "0.0.{p}", "0.0.{q}-beta.1+1"],
    ),
    (
        {"branches": {"main": {"label": "beta"}}},
        True,
        ["1.0.1-beta.1+1", "1.0.{p}-beta.1+1", "1.0.{p}-beta.1+2", "1.0.{p}-beta.1+3", "1.0.{p}-beta.1",
         "1.0.{p}-beta.2+1", "1.0.{p}-beta.2", "1.0.{p}-beta.3+1", "1.0.{p}", "1.0.{q}-beta.1+1"],
    ),
    # gamma label.
    (
        {"branches": {"main": {"label": "gamma"}}},
        False,
        ["0.0.1-gamma.1+1", "0.0.{p}-gamma.1+1", "0.0.{p}-gamma.1+2", "0.0.{p}-gamma.1+3", "0.0.{p}-gamma.1+4",
         "0.0.{p}-gamma.1+5", "0.0.{p}-gamma.1+6", "0.0.{p}-gamma.1+7", "0.0.{p}", "0.0.{q}-gamma.1+1"],
    ),
    (
        {"branches": {"main": {"label": "gamma"}}},
        True,
        ["1.0.1-gamma.1+1", "1.0.{p}-gamma.1+1", "1.0.{p}-gamma.1+2", "1.0.{p}-gamma.1+3", "1.0.{p}-gamma.1+4",
         "1.0.{p}-gamma.1+5", "1.0.{p}-gamma.1+6", "1.0.{p}-gamma.1+7", "1.0.{p}", "1.0.{q}-gamma.1+1"],
    ),
]  # fmt: skip


@pytest.mark.parametrize("patch", [1, 2, 3])
@pytest.mark.parametrize(("label_config", "initial_tag", "sequence"), _LABEL_SEQUENCES)
def test_ensure_pre_release_tag_label_will_be_considered(
    label_config: dict[str, Any], initial_tag: bool, sequence: list[str], patch: int
) -> None:
    if (
        initial_tag
        and patch == 1
        and label_config == {"label": None, "branches": {"main": {"label": None}}}
    ):
        pass  # upstream has a dedicated patch-1 test with identical expectations
    branches = {
        "main": {
            "mode": "ManualDeployment",
            "increment": "Patch",
            **label_config.get("branches", {})["main"],
        }
    }
    root = {k: v for k, v in label_config.items() if k != "branches"}
    c = githubflow(branches=branches, **root)
    base = "1.0" if initial_tag else "0.0"
    e = [s.format(p=patch, q=patch + 1) for s in sequence]
    with Scenario() as f:
        if initial_tag:
            f.make_a_tagged_commit("1.0.0")
        f.make_a_commit()
        f.assert_full_semver(e[0], c)
        f.apply_tag(f"{base}.{patch}-alpha.1")
        f.assert_full_semver(e[1], c)
        f.make_a_commit()
        f.assert_full_semver(e[2], c)
        f.make_a_commit()
        f.assert_full_semver(e[3], c)
        f.make_a_tagged_commit(f"{base}.{patch}-beta.1")
        f.assert_full_semver(e[4], c)
        f.make_a_commit()
        f.assert_full_semver(e[5], c)
        f.make_a_tagged_commit(f"{base}.{patch}-beta.2")
        f.assert_full_semver(e[6], c)
        f.make_a_commit()
        f.assert_full_semver(e[7], c)
        f.apply_tag(f"{base}.{patch}")
        f.assert_full_semver(e[8], c)
        f.make_a_commit()
        f.assert_full_semver(e[9], c)


@pytest.mark.parametrize("label", [None, ""])
def test_increase_version_with_bump_message_when_increment_is_none_for_branch_with_no_label(
    label: str | None,
) -> None:
    c = gitflow(
        label=None,
        branches={
            "main": {
                "commit_message_incrementing": "Enabled",
                "mode": "ContinuousDelivery",
                "increment": "None",
                "label": label,
                "is_main_branch": False,
            }
        },
    )
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("0.0.0-1", c)
        f.make_a_commit("+semver: minor")
        f.assert_full_semver("0.1.0-2", c)
        f.apply_tag("1.0.0")
        f.assert_full_semver("1.0.0", c)
        f.make_a_commit("+semver: major")
        f.assert_full_semver("2.0.0-1", c)
        f.apply_tag("2.0.0")
        f.make_a_commit()
        f.assert_full_semver("2.0.0-1", c)


def test_increase_version_with_bump_message_when_increment_is_none_for_branch_with_alpha_label() -> (
    None
):
    c = gitflow(
        branches={
            "main": {
                "commit_message_incrementing": "Enabled",
                "mode": "ContinuousDelivery",
                "increment": "None",
                "label": "pre",
                "is_main_branch": False,
            }
        }
    )
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("0.0.0-pre.1", c)
        f.make_a_commit("+semver: minor")
        f.assert_full_semver("0.1.0-pre.2", c)
        f.apply_tag("1.0.0")
        f.assert_full_semver("1.0.0", c)
        f.make_a_commit("+semver: major")
        f.assert_full_semver("2.0.0-pre.1", c)
        f.apply_tag("2.0.0")
        f.make_a_commit()
        f.assert_full_semver("2.0.0-pre.1", c)


def test_should_provide_the_correct_version_even_if_pre_release_label_exists_in_the_git_tag_main() -> (
    None
):
    c = gitflow(
        next_version="5.0",
        semantic_version_format="Loose",
        branches={
            "main": {
                "label": "beta",
                "increment": "Patch",
                "mode": "ContinuousDelivery",
                "is_main_branch": False,
            }
        },
    )
    with Scenario() as f:
        f.make_a_commit()
        f.assert_full_semver("5.0.0-beta.1", c)
        f.make_a_commit()
        f.assert_full_semver("5.0.0-beta.2", c)
        f.apply_tag("5.0.0-beta.3")
        f.assert_full_semver("5.0.0-beta.3", c)
        f.make_a_tagged_commit("5.0.0-rc.1")
        f.assert_full_semver("5.0.0-beta.4", c)
        f.make_a_commit()
        f.assert_full_semver("5.0.0-beta.5", c)


def test_ensure_the_pre_release_tag_is_correctly_generated_when_pre_release_label_is_empty() -> (
    None
):
    c = gitflow(
        branches={"main": {"label": "", "is_main_branch": False, "mode": "ContinuousDelivery"}}
    )
    with Scenario() as f:
        f.make_commits(5)
        f.get_version(c)
        f.assert_full_semver("0.0.1-5", c)


_PREVENT_CASES = {
    "ManualDeployment": [
        ("0.0.1-alpha.2", True, "0.0.1-alpha.2"),
        ("0.0.1-alpha.2", False, "0.0.1-alpha.3+0"),
        ("0.1.0-alpha.2", True, "0.1.0-alpha.2"),
        ("0.1.0-alpha.2", False, "0.1.0-alpha.3+0"),
        ("0.0.1", True, "0.0.1"),
        ("0.0.1", False, "0.1.0-alpha.1+0"),
        ("0.0.1-beta.2", True, "0.1.0-alpha.1+1"),
        ("0.0.1-beta.2", False, "0.1.0-alpha.1+1"),
        ("0.1.0-beta.2", True, "0.1.0-alpha.1+1"),
        ("0.1.0-beta.2", False, "0.1.0-alpha.1+1"),
        ("0.2.0-beta.2", True, "0.2.0-alpha.1+1"),
        ("0.2.0-beta.2", False, "0.2.0-alpha.1+1"),
    ],
    "ContinuousDelivery": [
        ("0.0.1-alpha.2", True, "0.0.1-alpha.2"),
        ("0.0.1-alpha.2", False, "0.0.1-alpha.2"),
        ("0.1.0-alpha.2", True, "0.1.0-alpha.2"),
        ("0.1.0-alpha.2", False, "0.1.0-alpha.2"),
        ("0.0.1", True, "0.0.1"),
        ("0.0.1", False, "0.1.0-alpha.0"),
        ("0.0.1-beta.2", True, "0.1.0-alpha.1"),
        ("0.0.1-beta.2", False, "0.1.0-alpha.1"),
        ("0.1.0-beta.2", True, "0.1.0-alpha.1"),
        ("0.1.0-beta.2", False, "0.1.0-alpha.1"),
        ("0.2.0-beta.2", True, "0.2.0-alpha.1"),
        ("0.2.0-beta.2", False, "0.2.0-alpha.1"),
    ],
    "ContinuousDeployment": [
        ("0.0.1-alpha.2", True, "0.0.1"),
        ("0.0.1-alpha.2", False, "0.0.1"),
        ("0.1.0-alpha.2", True, "0.1.0"),
        ("0.1.0-alpha.2", False, "0.1.0"),
        ("0.0.1", True, "0.0.1"),
        ("0.0.1", False, "0.1.0"),
        ("0.0.1-beta.2", True, "0.1.0"),
        ("0.0.1-beta.2", False, "0.1.0"),
        ("0.1.0-beta.2", True, "0.1.0"),
        ("0.1.0-beta.2", False, "0.1.0"),
        ("0.2.0-beta.2", True, "0.2.0"),
        ("0.2.0-beta.2", False, "0.2.0"),
    ],
}


@pytest.mark.parametrize(
    ("mode", "tag", "prevent", "expected"),
    [(mode, *case) for mode, cases in _PREVENT_CASES.items() for case in cases],
)
def test_ensure_prevent_increment_when_current_commit_tagged_on_develop(
    mode: str, tag: str, prevent: bool, expected: str
) -> None:
    c = gitflow(
        branches={
            "develop": {"mode": mode, "prevent_increment": {"when_current_commit_tagged": prevent}}
        }
    )
    with Scenario() as f:
        f.make_a_commit("A")
        if tag:
            f.apply_tag(tag)
        f.branch_to("develop")
        f.assert_full_semver(expected, c)


@pytest.mark.parametrize(("prevent", "expected"), [(True, "1.0.0"), (False, "6.0.0-alpha.1+0")])
def test_ensure_prevent_increment_when_current_commit_tagged_on_develop_with_next_version(
    prevent: bool, expected: str
) -> None:
    c = gitflow(
        next_version="6.0.0",
        branches={
            "develop": {
                "mode": "ManualDeployment",
                "prevent_increment": {"when_current_commit_tagged": prevent},
            }
        },
    )
    with Scenario() as f:
        f.make_a_commit()
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("develop")
        f.assert_full_semver(expected, c)


_RELEASE_PREVENT_CASES: list[tuple[list[str] | None, bool, str]] = [
    (None, True, "6.0.0-beta.1+1"),
    (None, False, "6.0.0-beta.1+1"),
    (["5.0.0"], True, "5.0.0"),
    (["5.0.0"], False, "6.0.0-beta.1+0"),
    (["6.0.0"], True, "6.0.0"),
    (["6.0.0"], False, "6.1.0-beta.1+0"),
    (["7.0.0"], True, "7.0.0"),
    (["7.0.0"], False, "7.1.0-beta.1+0"),
    (["5.0.0-alpha.2"], True, "6.0.0-beta.1+1"),
    (["5.0.0-alpha.2"], False, "6.0.0-beta.1+1"),
    (["6.0.0-alpha.2"], True, "6.0.0-beta.1+1"),
    (["6.0.0-alpha.2"], False, "6.0.0-beta.1+1"),
    (["7.0.0-alpha.2"], True, "7.0.0-beta.1+1"),
    (["7.0.0-alpha.2"], False, "7.0.0-beta.1+1"),
    (["5.0.0-beta.2"], True, "5.0.0-beta.2"),
    (["5.0.0-beta.2"], False, "6.0.0-beta.1+0"),
    (["6.0.0-beta.2"], True, "6.0.0-beta.2"),
    (["6.0.0-beta.2"], False, "6.0.0-beta.3+0"),
    (["7.0.0-beta.2"], True, "7.0.0-beta.2"),
    (["7.0.0-beta.2"], False, "7.0.0-beta.3+0"),
    (["5.0.0", "6.0.0"], True, "6.0.0"),
    (["5.0.0", "6.0.0"], False, "6.1.0-beta.1+0"),
    (["6.0.0", "5.0.0"], True, "6.0.0"),
    (["6.0.0", "5.0.0"], False, "6.1.0-beta.1+0"),
    (["6.0.0", "7.0.0"], True, "7.0.0"),
    (["6.0.0", "7.0.0"], False, "7.1.0-beta.1+0"),
    (["7.0.0", "6.0.0"], True, "7.0.0"),
    (["7.0.0", "6.0.0"], False, "7.1.0-beta.1+0"),
    (["4.0.0", "5.0.0-alpha.2"], True, "4.0.0"),
    (["4.0.0", "5.0.0-alpha.2"], False, "6.0.0-beta.1+0"),
    (["5.0.0-alpha.2", "4.0.0"], True, "4.0.0"),
    (["5.0.0-alpha.2", "4.0.0"], False, "6.0.0-beta.1+0"),
    (["4.0.0", "5.0.0-beta.2"], True, "5.0.0-beta.2"),
    (["4.0.0", "5.0.0-beta.2"], False, "6.0.0-beta.1+0"),
    (["5.0.0-beta.2", "4.0.0"], True, "5.0.0-beta.2"),
    (["5.0.0-beta.2", "4.0.0"], False, "6.0.0-beta.1+0"),
    (["4.0.0-alpha.2", "5.0.0-beta.2"], True, "5.0.0-beta.2"),
    (["4.0.0-alpha.2", "5.0.0-beta.2"], False, "6.0.0-beta.1+0"),
    (["5.0.0-beta.2", "4.0.0-alpha.2"], True, "5.0.0-beta.2"),
    (["5.0.0-beta.2", "4.0.0-alpha.2"], False, "6.0.0-beta.1+0"),
]


@pytest.mark.parametrize(("tags", "prevent", "expected"), _RELEASE_PREVENT_CASES)
def test_ensure_prevent_increment_when_current_commit_tagged_on_release_branch_and_increment_minor(
    tags: list[str] | None, prevent: bool, expected: str
) -> None:
    c = gitflow(
        branches={
            "release": {
                "mode": "ManualDeployment",
                "prevent_increment": {"when_current_commit_tagged": prevent},
                "increment": "Minor",
            }
        }
    )
    with Scenario() as f:
        f.make_a_commit()
        for tag in tags or []:
            f.apply_tag(tag)
        f.branch_to("release/6.0.0")
        f.assert_full_semver(expected, c)


def test_ensure_version_after_main_is_merged_back_to_develop_is_correct() -> None:
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.branch_to("develop")
        f.make_a_commit("A")
        f.assert_full_semver("1.1.0-alpha.1")
        f.checkout("main")
        f.make_a_commit("B")
        f.branch_to("hotfix/just-a-hotfix")
        f.make_a_commit("C +semver: major")
        f.merge_to("main")
        f.delete_branch("hotfix/just-a-hotfix")
        f.checkout("develop")
        f.make_a_commit("D")
        f.checkout("main")
        f.make_a_commit("E")
        f.apply_tag("1.0.1")
        f.checkout("develop")
        f.merge_no_ff("main")
        f.assert_full_semver("1.1.0-alpha.3")


@pytest.mark.parametrize("apply_tag", [False, True])
def test_ensure_version_after_main_is_merged_back_to_develop_is_correct_for_mainline(
    apply_tag: bool,
) -> None:
    c = gitflow(strategies=["Mainline"])
    with Scenario() as f:
        f.make_a_commit("A")
        f.apply_tag("1.0.0")
        f.branch_to("develop")
        f.make_a_commit("B +semver: major")
        f.assert_full_semver("2.0.0-alpha.1", c)
        f.checkout("main")
        f.make_a_commit("C")
        if apply_tag:
            f.apply_tag("1.0.1")
        f.checkout("develop")
        f.merge_no_ff("main")
        f.assert_full_semver("2.0.0-alpha.2", c)


@pytest.mark.parametrize(
    ("apply_tag", "expected"), [(False, "2.0.0-alpha.3"), (True, "3.0.0-alpha.2")]
)
def test_ensure_version_after_main_is_merged_back_to_develop_is_correct_for_gitflow(
    apply_tag: bool, expected: str
) -> None:
    c = gitflow()
    with Scenario() as f:
        f.make_a_commit("A")
        f.apply_tag("1.0.0")
        f.branch_to("develop")
        f.make_a_commit("B +semver: major")
        f.assert_full_semver("2.0.0-alpha.1", c)
        f.checkout("main")
        f.make_a_commit("C")
        if apply_tag:
            f.apply_tag("2.0.0")
        f.checkout("develop")
        f.merge_no_ff("main")
        f.assert_full_semver(expected, c)


def test_ensure_version_source_is_set_to_the_right_tag() -> None:
    c = gitflow()
    with GitFlowScenario("0.1.0") as f:
        f.checkout("main")
        f.merge_no_ff("develop")
        f.checkout("develop")
        f.make_a_commit("Feature commit 1")
        f.branch_to("release/0.2.0")
        f.make_a_commit("Release commit 1")
        f.checkout("main")
        f.merge_no_ff("release/0.2.0")
        f.apply_tag("0.2.0")
        tag_sha = f.head_sha
        f.checkout("develop")
        f.merge_no_ff("main")
        assert f.get_version(c)["VersionSourceSha"] == tag_sha


def test_unversioned_hotfix() -> None:
    c = gitflow()
    with GitFlowScenario("1.2.0") as f:
        f.checkout("main")
        f.branch_to("hotfix/put-out-the-fire")
        f.make_a_commit()
        f.assert_full_semver("1.2.1-beta.1+1", c)
        f.make_a_commit()
        f.assert_full_semver("1.2.1-beta.1+2", c)
        f.checkout("main")
        f.merge_no_ff("hotfix/put-out-the-fire")
        f.assert_full_semver("1.2.1-3", c)


def test_alternative_semantic_versions_should_be_considered() -> None:
    with Scenario() as f:
        f.make_a_commit("A")
        f.make_a_tagged_commit("4.0.0-beta.14")
        f.make_a_commit("B")
        f.assert_full_semver("4.0.0-3", gitflow())


@pytest.mark.parametrize(
    ("label_on_main", "expected"),
    [(None, "6.0.0-beta.6"), ("beta", "6.0.0-beta.6"), ("gamma", "6.0.0-gamma.21")],
)
def test_alternative_semantic_versions_should_be_considered_with_labels(
    label_on_main: str | None, expected: str
) -> None:
    c = gitflow(label=None, branches={"main": {"label": label_on_main}})
    with Scenario() as f:
        f.make_a_tagged_commit("1.0.0")
        f.make_a_commit("A")
        f.apply_tag("4.0.0-beta.14")
        f.apply_tag("4.0.0-gamma.14")
        f.make_a_commit("B")
        f.make_a_tagged_commit("6.0.0-alpha.1")
        f.make_a_tagged_commit("6.0.0-alpha.2")
        f.make_a_tagged_commit("6.0.0-alpha.3")
        f.make_a_commit("C")
        f.make_a_tagged_commit("6.0.0-beta.5")
        f.make_a_commit("D")
        f.assert_full_semver(expected, c)
