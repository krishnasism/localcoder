from main import _resolve_cd_command


def test_resolve_cd_command_relative(tmp_path):
    child = tmp_path / "child"
    child.mkdir()
    base = str(tmp_path)

    result = _resolve_cd_command("cd child", base)

    assert result is not None
    assert result["returncode"] == 0
    assert result["cwd"] == str(child.resolve())
    assert str(child.resolve()) in result["stdout"]


def test_resolve_cd_command_parent(tmp_path):
    child = tmp_path / "child"
    child.mkdir()
    base = str(child)

    result = _resolve_cd_command("cd ..", base)

    assert result is not None
    assert result["returncode"] == 0
    assert result["cwd"] == str(tmp_path.resolve())


def test_resolve_cd_command_missing_path(tmp_path):
    result = _resolve_cd_command("cd missing-folder", str(tmp_path))

    assert result is not None
    assert result["returncode"] == 1
    assert result["cwd"] == str(tmp_path.resolve())
    assert "cannot find the path" in result["stderr"].lower()


def test_resolve_cd_command_not_a_cd(tmp_path):
    result = _resolve_cd_command("ls", str(tmp_path))
    assert result is None


def test_resolve_cd_command_powershell_alias(tmp_path):
    child = tmp_path / "child"
    child.mkdir()

    result = _resolve_cd_command("Set-Location child", str(tmp_path))

    assert result is not None
    assert result["returncode"] == 0
    assert result["cwd"] == str(child.resolve())
