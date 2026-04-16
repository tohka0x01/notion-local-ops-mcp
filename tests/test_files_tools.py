from pathlib import Path

from notion_local_ops_mcp.files import list_files, read_file, read_files, replace_in_file, write_file
from notion_local_ops_mcp.pathing import resolve_path


def test_resolve_path_uses_workspace_root_for_relative_paths(tmp_path: Path) -> None:
    resolved = resolve_path("src/app.py", tmp_path)
    assert resolved == (tmp_path / "src/app.py").resolve()


def test_list_files_returns_direct_children(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "nested").mkdir()

    result = list_files(tmp_path, recursive=False, limit=20)

    assert result["success"] is True
    assert {entry["name"] for entry in result["entries"]} == {"a.txt", "nested"}
    assert result["truncated"] is False


def test_list_files_supports_offset_pagination(tmp_path: Path) -> None:
    for name in ("a.txt", "b.txt", "c.txt"):
        (tmp_path / name).write_text(name, encoding="utf-8")

    result = list_files(tmp_path, recursive=False, limit=1, offset=1)

    assert result["success"] is True
    assert [entry["name"] for entry in result["entries"]] == ["b.txt"]
    assert result["truncated"] is True
    assert result["next_offset"] == 2


def test_read_file_supports_offset_and_limit(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")

    result = read_file(target, offset=2, limit=2, max_lines=50, max_bytes=4096)

    assert result["success"] is True
    assert result["content"] == "two\nthree"
    assert result["next_offset"] == 4


def test_read_files_returns_multiple_results_in_order(tmp_path: Path) -> None:
    first = tmp_path / "one.txt"
    second = tmp_path / "two.txt"
    first.write_text("alpha\nbeta\n", encoding="utf-8")
    second.write_text("gamma\ndelta\n", encoding="utf-8")

    result = read_files([first, second], offset=1, limit=1, max_lines=50, max_bytes=4096)

    assert result["success"] is True
    assert [item["path"] for item in result["results"]] == [str(first), str(second)]
    assert [item["content"] for item in result["results"]] == ["alpha", "gamma"]


def test_write_file_creates_parent_directories(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "file.txt"

    result = write_file(target, content="hello")

    assert result["success"] is True
    assert target.read_text(encoding="utf-8") == "hello"
    assert result["bytes_written"] == 5


def test_replace_in_file_requires_unique_match(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("print('before')\n", encoding="utf-8")

    result = replace_in_file(target, old_text="before", new_text="after")

    assert result["success"] is True
    assert "after" in target.read_text(encoding="utf-8")
    assert result["replacements"] == 1


def test_replace_in_file_can_replace_all_matches(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("before\nbefore\n", encoding="utf-8")

    result = replace_in_file(target, old_text="before", new_text="after", replace_all=True)

    assert result["success"] is True
    assert target.read_text(encoding="utf-8") == "after\nafter\n"
    assert result["replacements"] == 2
