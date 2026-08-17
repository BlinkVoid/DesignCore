import json
from pathlib import Path

import pytest
import yaml

BUNDLES = ["architecture-diagram", "flow-diagram", "concept-sketch"]


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} has no YAML frontmatter"
    return yaml.safe_load(text.split("---\n")[1])


@pytest.mark.parametrize("bundle", BUNDLES)
def test_bundle_has_skill_and_manifest(bundle):
    root = Path("skills") / bundle
    assert (root / "SKILL.md").exists()
    assert (root / "manifest.json").exists()


@pytest.mark.parametrize("bundle", BUNDLES)
def test_frontmatter_name_matches_directory(bundle):
    data = _frontmatter(Path("skills") / bundle / "SKILL.md")
    assert data["name"] == bundle
    assert data["description"].strip()


@pytest.mark.parametrize("bundle", BUNDLES)
def test_manifest_is_valid_json_naming_the_bundle(bundle):
    data = json.loads((Path("skills") / bundle / "manifest.json").read_text(encoding="utf-8"))
    assert data["name"] == bundle
    assert data["category"] == "design"
    assert data["activation"]["triggers"]


@pytest.mark.parametrize("bundle", BUNDLES)
def test_skill_states_the_two_hard_rules(bundle):
    text = (Path("skills") / bundle / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "never" in text and "coordinate" in text
    assert "render" in text


@pytest.mark.parametrize("bundle", BUNDLES)
def test_skill_links_shared_references(bundle):
    text = (Path("skills") / bundle / "SKILL.md").read_text(encoding="utf-8")
    assert "_shared/references/pipeline.md" in text
    assert "_shared/references/legibility.md" in text
