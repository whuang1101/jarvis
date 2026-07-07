from __future__ import annotations

from jarvis import plugins
from jarvis.plugins import discover_plugins


class TestPluginDiscovery:
    def _make_plugin_dirs(self, tmp_path, monkeypatch):
        root = tmp_path / "plugins"
        root.mkdir()

        full = root / "full-plugin"
        full.mkdir()
        (full / "plugin.toml").write_text(
            'name = "full"\ndescription = "a full plugin"\nversion = "1.2.3"\n'
        )

        empty = root / "empty-plugin"
        empty.mkdir()
        (empty / "plugin.toml").write_text("")

        junk = root / "junk"
        junk.mkdir()
        (junk / "README.md").write_text("not a plugin")

        monkeypatch.setattr(plugins, "_plugin_roots", lambda: (root, tmp_path / "nonexistent"))
        return root

    def test_discovers_valid_plugins_and_skips_junk(self, tmp_path, monkeypatch):
        self._make_plugin_dirs(tmp_path, monkeypatch)

        found = {p.name: p for p in discover_plugins()}
        assert set(found) == {"full", "empty-plugin"}
        assert found["full"].description == "a full plugin"
        assert found["full"].version == "1.2.3"
        assert found["empty-plugin"].description == ""
        assert found["empty-plugin"].version == ""

    def test_skips_malformed_manifest_without_raising(self, tmp_path, monkeypatch):
        root = self._make_plugin_dirs(tmp_path, monkeypatch)

        broken = root / "broken-plugin"
        broken.mkdir()
        (broken / "plugin.toml").write_text("this is not [valid toml")

        found = {p.name: p for p in discover_plugins()}
        assert "broken-plugin" not in found
        assert set(found) == {"full", "empty-plugin"}

    def test_project_plugin_shadows_global_plugin_of_same_name(self, tmp_path, monkeypatch):
        global_root = tmp_path / "global"
        project_root = tmp_path / "project"
        global_root.mkdir()
        project_root.mkdir()

        global_plugin = global_root / "shared"
        global_plugin.mkdir()
        (global_plugin / "plugin.toml").write_text('name = "shared"\ndescription = "global"\n')

        project_plugin = project_root / "shared"
        project_plugin.mkdir()
        (project_plugin / "plugin.toml").write_text('name = "shared"\ndescription = "project"\n')

        monkeypatch.setattr(plugins, "_plugin_roots", lambda: (global_root, project_root))

        found = {p.name: p for p in discover_plugins()}
        assert set(found) == {"shared"}
        assert found["shared"].description == "project"
