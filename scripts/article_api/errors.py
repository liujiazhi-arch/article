from __future__ import annotations

from typing import Any


def classify_error_message(message: str) -> str:
    if "文件不存在" in message:
        return "missing_file"
    if "仅支持 .docx" in message or "Only .docx" in message:
        return "unsupported_file_type"
    if "Only .pdf" in message:
        return "unsupported_pdf_type"
    if "不是有效的 .pdf" in message or "Uploaded .pdf file is empty" in message:
        return "invalid_pdf"
    if "不是有效的 .docx" in message or "word/document.xml" in message:
        return "invalid_docx"
    return "bad_request"


def user_message_for_code(code: str, raw_message: str) -> str:
    if code == "missing_file":
        return "找不到要处理的文件。"
    if code == "unsupported_file_type":
        return "目前只支持 .docx 格式的 Word 文档。"
    if code == "unsupported_pdf_type":
        return "目前只支持 PDF 格式的文件。"
    if code == "invalid_docx":
        return "上传的文件不是有效的 DOCX 文档。"
    if code == "invalid_pdf":
        return "上传的文件不是有效的 PDF 文档。"
    if code == "worker_timeout":
        return "任务处理超时。"
    if code == "internal_error":
        return "后端处理任务时出现内部错误。"
    if code == "apply_guard_blocked":
        return "当前文档存在结构风险，已阻止自动修复。"
    if code == "artifact_not_found":
        return "没有找到这个下载项。"
    if code == "artifact_unavailable":
        return "下载文件已经不可用。"
    if code == "upload_not_found":
        return "没有找到这个上传记录。"
    if code == "upload_unavailable":
        return "上传文件已经不可用。"
    return raw_message or "请求无法处理。"


def next_action_for_code(code: str) -> str:
    if code == "missing_file":
        return "请确认文件仍在原路径，或重新上传论文后再试。"
    if code == "unsupported_file_type":
        return "请先用 Word/WPS 将文档另存为 .docx，再重新上传。"
    if code == "unsupported_pdf_type":
        return "请从 Word/WPS 导出 .pdf 文件后再上传。"
    if code == "invalid_docx":
        return "请在 Word/WPS 中打开原文档，另存为 .docx 后重新上传；如果仍失败，请换一个干净副本。"
    if code == "invalid_pdf":
        return "请从 Word/WPS 重新导出 PDF 后再上传。"
    if code == "worker_timeout":
        return "可以缩小 scope 后重试，或稍后重新提交任务。"
    if code == "internal_error":
        return "请保留当前文档和任务编号，稍后重试；如果重复失败，请把错误信息发给维护者。"
    if code == "apply_guard_blocked":
        return "请先人工检查标题层级、目录和图表位置；确认风险可接受后再考虑强制修复。"
    if code == "artifact_not_found":
        return "请刷新任务结果后重试；如果仍看不到下载项，请重新运行对应任务。"
    if code == "artifact_unavailable":
        return "请重新运行修复任务后再下载；如果刚做过清理，需要重新生成修复稿。"
    if code in {"upload_not_found", "upload_unavailable"}:
        return "请重新上传论文后再试。"
    return "请检查输入后重试。"


def retryable_for_code(code: str) -> bool:
    return code in {"internal_error", "worker_timeout"}


def http_status_for_code(code: str) -> int:
    if code in {"missing_file", "unsupported_file_type", "unsupported_pdf_type", "invalid_docx", "invalid_pdf", "bad_request"}:
        return 400
    if code == "worker_timeout":
        return 504
    if code == "internal_error":
        return 500
    if code == "artifact_not_found":
        return 404
    if code == "upload_not_found":
        return 404
    return 409


def error_payload(
    code: str,
    *,
    exc_type: str,
    message: str,
    http_status: int | None = None,
    retryable: bool | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "type": exc_type,
        "message": message,
        "user_message": user_message_for_code(code, message),
        "next_action": next_action_for_code(code),
        "http_status": http_status if http_status is not None else http_status_for_code(code),
        "retryable": retryable if retryable is not None else retryable_for_code(code),
    }
    if extra:
        payload.update(extra)
    return payload


def value_error_payload(exc: ValueError) -> dict[str, Any]:
    message = str(exc)
    code = classify_error_message(message)
    return error_payload(code, exc_type=type(exc).__name__, message=message)


def runtime_error_payload(exc: RuntimeError) -> dict[str, Any]:
    message = str(exc)
    return error_payload(
        "internal_error",
        exc_type=type(exc).__name__,
        message=message,
        http_status=409,
        retryable=False,
    )


def upload_error_payload(exc: Exception) -> dict[str, Any] | None:
    message = str(exc)
    if message.startswith("Upload not found"):
        code = "upload_not_found"
    elif message.startswith("Uploaded file is unavailable"):
        code = "upload_unavailable"
    else:
        return None
    return error_payload(
        code,
        exc_type=type(exc).__name__,
        message=message,
        retryable=False,
    )


def artifact_download_error_payload(exc: Exception) -> dict[str, Any] | None:
    message = str(exc)
    if message.startswith("Artifact not found"):
        code = "artifact_not_found"
    elif message.startswith("Artifact file is unavailable") or message.startswith("Artifact download is only available"):
        code = "artifact_unavailable"
    else:
        return None
    return error_payload(
        code,
        exc_type=type(exc).__name__,
        message=message,
        retryable=False,
    )


def normalize_error_payload(error: dict[str, Any]) -> dict[str, Any]:
    code = str(error.get("code") or "internal_error")
    message = str(error.get("message") or "")
    normalized = dict(error)
    normalized.setdefault("type", "RuntimeError")
    normalized.setdefault("message", message)
    normalized.setdefault("user_message", user_message_for_code(code, message))
    normalized.setdefault("next_action", next_action_for_code(code))
    normalized.setdefault("http_status", http_status_for_code(code))
    normalized.setdefault("retryable", retryable_for_code(code))
    return normalized
