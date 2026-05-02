from io import BytesIO
from pathlib import Path

import pytest

from article_api.uploads import (
    build_job_workspace,
    infer_uploaded_docx_name,
    resolve_runtime_root,
    stage_local_docx,
    store_uploaded_docx,
)

from .conftest import make_compliant_doc


def test_stage_local_docx_copies_source_into_runtime(tmp_docx, tmp_path):
    runtime_root = tmp_path / "runtime"
    source_path = tmp_docx(make_compliant_doc, filename="article_upload_source.docx")

    staged = stage_local_docx(str(source_path), runtime_root=runtime_root)

    assert staged.file_name == "article_upload_source.docx"
    assert staged.source_path == str(Path(source_path).resolve())
    assert Path(staged.staged_path).exists()
    assert Path(staged.staged_path).read_bytes() == Path(source_path).read_bytes()
    assert Path(staged.workspace_dir) == runtime_root / "staging"


def test_stage_local_docx_creates_distinct_copies(tmp_docx, tmp_path):
    runtime_root = tmp_path / "runtime"
    source_path = tmp_docx(make_compliant_doc, filename="article_upload_distinct.docx")

    first = stage_local_docx(str(source_path), runtime_root=runtime_root)
    second = stage_local_docx(str(source_path), runtime_root=runtime_root)

    assert first.staged_path != second.staged_path
    assert Path(first.staged_path).exists()
    assert Path(second.staged_path).exists()


def test_stage_local_docx_rejects_invalid_path(tmp_path):
    runtime_root = tmp_path / "runtime"
    missing_path = tmp_path / "missing.docx"

    with pytest.raises(ValueError, match="文件不存在"):
        stage_local_docx(str(missing_path), runtime_root=runtime_root)


def test_build_job_workspace_creates_inputs_and_outputs(tmp_path):
    workspace = build_job_workspace("job-123", runtime_root=tmp_path / "runtime")

    assert Path(workspace["root"]).exists()
    assert Path(workspace["inputs"]).exists()
    assert Path(workspace["outputs"]).exists()


def test_resolve_runtime_root_creates_default_runtime_dir(monkeypatch):
    monkeypatch.delenv("ARTICLE_API_RUNTIME_ROOT", raising=False)
    root = resolve_runtime_root()

    assert root.exists()
    assert root.name == ".article_runtime"


def test_store_uploaded_docx_writes_upload_into_runtime(tmp_path):
    runtime_root = tmp_path / "runtime"

    class FakeUpload:
        filename = "article_upload_http.docx"

        def __init__(self):
            self.file = BytesIO(b"fake-docx-binary")

    stored = store_uploaded_docx(FakeUpload(), runtime_root=runtime_root)

    assert stored.file_name == "article_upload_http.docx"
    assert stored.size_bytes == len(b"fake-docx-binary")
    assert Path(stored.stored_path).exists()
    assert Path(stored.workspace_dir) == runtime_root / "uploads"


def test_store_uploaded_docx_preserves_chinese_upload_name(tmp_path):
    runtime_root = tmp_path / "runtime"

    class FakeUpload:
        filename = "20221303306-刘佳轾-不同改性方法对鹿皮明胶功能特性和结构特性的影响研究_摘要替换版.docx"

        def __init__(self):
            self.file = BytesIO(b"fake-docx-binary")

    stored = store_uploaded_docx(FakeUpload(), runtime_root=runtime_root)

    assert stored.file_name == FakeUpload.filename
    assert Path(stored.stored_path).name.endswith(FakeUpload.filename)
    assert infer_uploaded_docx_name(stored.stored_path) == FakeUpload.filename


def test_store_uploaded_docx_rejects_non_docx_name(tmp_path):
    runtime_root = tmp_path / "runtime"

    class FakeUpload:
        filename = "article_upload_http.txt"

        def __init__(self):
            self.file = BytesIO(b"bad")

    with pytest.raises(ValueError, match="Only .docx uploads are supported"):
        store_uploaded_docx(FakeUpload(), runtime_root=runtime_root)


def test_infer_uploaded_docx_name_restores_original_filename(tmp_path):
    stored_path = tmp_path / "uploads" / "1234567890abcdef1234567890abcdef_article_upload_http.docx"
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    stored_path.write_bytes(b"fake-docx-binary")

    assert infer_uploaded_docx_name(stored_path) == "article_upload_http.docx"
