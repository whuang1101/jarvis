from __future__ import annotations

from pathlib import Path

from jarvis.skills import discover_skills, load_skill


class TestSkillDiscovery:
    def _make_skill_dirs(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        project = tmp_path / "project"
        global_dir = home / ".jarvis" / "skills"
        project_dir = project / ".jarvis" / "skills"
        global_dir.mkdir(parents=True)
        project_dir.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: home)
        monkeypatch.chdir(project)
        return global_dir, project_dir

    def test_discovers_flat_and_dir_style_skills(self, tmp_path, monkeypatch):
        global_dir, project_dir = self._make_skill_dirs(tmp_path, monkeypatch)

        (global_dir / "hello.md").write_text(
            "---\nname: hello\ndescription: says hello\n---\nHello body.\n"
        )

        nested = project_dir / "review"
        nested.mkdir()
        (nested / "SKILL.md").write_text(
            "---\nname: review\ndescription: reviews things\n---\nReview body.\n"
        )

        found = {s.name: s for s in discover_skills()}
        assert set(found) == {"hello", "review"}
        assert found["hello"].description == "says hello"
        assert found["hello"].body == "Hello body.\n"
        assert found["review"].description == "reviews things"
        assert found["review"].body == "Review body.\n"

    def test_project_skill_shadows_global_skill_of_same_name(self, tmp_path, monkeypatch):
        global_dir, project_dir = self._make_skill_dirs(tmp_path, monkeypatch)

        (global_dir / "shared.md").write_text(
            "---\ndescription: global version\n---\nGlobal body.\n"
        )
        (project_dir / "shared.md").write_text(
            "---\ndescription: project version\n---\nProject body.\n"
        )

        found = discover_skills()
        assert len(found) == 1
        assert found[0].name == "shared"
        assert found[0].description == "project version"
        assert found[0].body == "Project body.\n"

    def test_missing_frontmatter_falls_back_to_stem_and_empty_description(
        self, tmp_path, monkeypatch
    ):
        global_dir, _ = self._make_skill_dirs(tmp_path, monkeypatch)
        (global_dir / "plain.md").write_text("Just a body, no frontmatter.\n")

        found = discover_skills()
        assert len(found) == 1
        assert found[0].name == "plain"
        assert found[0].description == ""
        assert found[0].body == "Just a body, no frontmatter.\n"

    def test_results_sorted_by_name(self, tmp_path, monkeypatch):
        global_dir, _ = self._make_skill_dirs(tmp_path, monkeypatch)
        (global_dir / "zeta.md").write_text("Zeta body.\n")
        (global_dir / "alpha.md").write_text("Alpha body.\n")

        found = discover_skills()
        assert [s.name for s in found] == ["alpha", "zeta"]

    def test_load_skill_returns_matching_skill(self, tmp_path, monkeypatch):
        global_dir, _ = self._make_skill_dirs(tmp_path, monkeypatch)
        (global_dir / "hello.md").write_text(
            "---\ndescription: says hello\n---\nHello body.\n"
        )

        skill = load_skill("hello")
        assert skill is not None
        assert skill.name == "hello"
        assert skill.description == "says hello"

    def test_load_skill_returns_none_when_missing(self, tmp_path, monkeypatch):
        self._make_skill_dirs(tmp_path, monkeypatch)
        assert load_skill("missing") is None
