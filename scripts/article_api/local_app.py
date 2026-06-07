from __future__ import annotations

import argparse
import json
import sys
import zipfile

from . import app as app_module
from . import local_env as local_env_module
from .local_backup import create_backup_archive, restore_backup_archive
from .local_doctor import build_doctor_report
from .local_env import root_env_scope
from .local_feedback import create_feedback_archive
from .local_maintenance import run_storage_maintenance
from .profiles import build_profile_catalog as build_profile_catalog_payload

_DEFAULT_CURRENT_COMMAND_BIN_DIR = local_env_module.current_command_bin_dir
_current_command_bin_dir = _DEFAULT_CURRENT_COMMAND_BIN_DIR
resolve_runtime_root = local_env_module.resolve_runtime_root


def _emit_json(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except UnicodeEncodeError:
        stdout_buffer = getattr(sys.stdout, "buffer", None)
        if stdout_buffer is None:
            raise
        stdout_buffer.write(text.encode("utf-8"))
        stdout_buffer.flush()


def initialize_local_workspace(
    *,
    state_root: str | None = None,
    runtime_root: str | None = None,
    write_env: str | None = None,
    overwrite_env: bool = False,
) -> dict:
    previous_command_bin_dir = local_env_module.current_command_bin_dir
    if _current_command_bin_dir is not _DEFAULT_CURRENT_COMMAND_BIN_DIR:
        local_env_module.current_command_bin_dir = _current_command_bin_dir
    try:
        return local_env_module.initialize_local_workspace(
            state_root=state_root,
            runtime_root=runtime_root,
            write_env=write_env,
            overwrite_env=overwrite_env,
        )
    finally:
        local_env_module.current_command_bin_dir = previous_command_bin_dir


def build_profile_catalog() -> dict:
    return build_profile_catalog_payload(
        service_name=app_module.SERVICE_NAME,
        stage=app_module.SERVICE_STAGE,
        version=app_module.SERVICE_VERSION,
        api_version=app_module.API_VERSION,
    )


def build_render_workflow_modes() -> dict:
    return app_module.build_render_workflow_modes_payload()


def run_preflight(
    file_path: str,
    *,
    profile: str = "lnu",
    strict_profile: bool | None = None,
) -> dict:
    return app_module.build_preflight_payload(
        file_path=file_path,
        profile_path=profile,
        strict_profile=strict_profile,
    )


def run_normalize(
    file_path: str,
    *,
    output_path: str | None = None,
    profile: str = "lnu",
    strict_profile: bool | None = None,
) -> dict:
    return app_module.build_normalize_payload(
        file_path=file_path,
        output_path=output_path,
        profile_path=profile,
        strict_profile=strict_profile,
    )


def run_render_verify(
    file_path: str,
    *,
    output_dir: str | None = None,
    profile: str = "lnu",
    strict_profile: bool | None = None,
    scopes=None,
    renderer: str = "auto",
    rendered_pdf: str | None = None,
    page_images_dir: str | None = None,
    workflow_mode: str | None = None,
) -> dict:
    return app_module.build_render_verify_payload(
        file_path=file_path,
        output_dir=output_dir,
        profile_path=profile,
        strict_profile=strict_profile,
        scopes=scopes,
        renderer=renderer,
        rendered_pdf=rendered_pdf,
        page_images_dir=page_images_dir,
        workflow_mode=workflow_mode,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="article-local")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--state-root")
    init_parser.add_argument("--runtime-root")
    init_parser.add_argument("--write-env")
    init_parser.add_argument("--overwrite-env", action="store_true")
    init_parser.set_defaults(handler=_handle_init)

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", default=8000, type=int)
    serve_parser.add_argument("--reload", action="store_true")
    serve_parser.add_argument("--state-root")
    serve_parser.add_argument("--runtime-root")
    serve_parser.set_defaults(handler=_handle_serve)

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--state-root")
    doctor_parser.add_argument("--runtime-root")
    doctor_parser.set_defaults(handler=_handle_doctor)

    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("input")
    preflight_parser.add_argument("--profile", default="lnu")
    preflight_parser.add_argument("--strict-profile", dest="strict_profile", action="store_true", default=None)
    preflight_parser.add_argument("--allow-profile-fallback", dest="strict_profile", action="store_false")
    preflight_parser.set_defaults(handler=_handle_preflight)

    normalize_parser = subparsers.add_parser("normalize")
    normalize_parser.add_argument("input")
    normalize_parser.add_argument("--output")
    normalize_parser.add_argument("--profile", default="lnu")
    normalize_parser.add_argument("--strict-profile", dest="strict_profile", action="store_true", default=None)
    normalize_parser.add_argument("--allow-profile-fallback", dest="strict_profile", action="store_false")
    normalize_parser.set_defaults(handler=_handle_normalize)

    render_verify_parser = subparsers.add_parser("render-verify")
    render_verify_parser.add_argument("input")
    render_verify_parser.add_argument("--profile", default="lnu")
    render_verify_parser.add_argument("--strict-profile", dest="strict_profile", action="store_true", default=None)
    render_verify_parser.add_argument("--allow-profile-fallback", dest="strict_profile", action="store_false")
    render_verify_parser.add_argument("--output-dir")
    render_verify_parser.add_argument("--scope", action="append", default=None)
    render_verify_parser.add_argument("--renderer", choices=["auto", "word-pdf"], default="auto")
    render_verify_parser.add_argument("--rendered-pdf")
    render_verify_parser.add_argument("--page-images-dir")
    render_verify_parser.add_argument("--workflow-mode", choices=["default_user", "agent_candidate"])
    render_verify_parser.set_defaults(handler=_handle_render_verify)

    render_workflow_parser = subparsers.add_parser("render-workflow-modes")
    render_workflow_parser.set_defaults(handler=_handle_render_workflow_modes)

    profiles_parser = subparsers.add_parser("profiles")
    profiles_parser.set_defaults(handler=_handle_profiles)

    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("output")
    backup_parser.add_argument("--state-root")
    backup_parser.add_argument("--runtime-root")
    backup_parser.set_defaults(handler=_handle_backup)

    feedback_parser = subparsers.add_parser("feedback")
    feedback_parser.add_argument("output")
    feedback_parser.add_argument("--state-root")
    feedback_parser.add_argument("--runtime-root")
    feedback_parser.set_defaults(handler=_handle_feedback)

    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("archive")
    restore_parser.add_argument("--state-root")
    restore_parser.add_argument("--runtime-root")
    restore_parser.add_argument("--force", action="store_true")
    restore_parser.set_defaults(handler=_handle_restore)

    maintain_parser = subparsers.add_parser("maintain")
    maintain_parser.add_argument("--state-root")
    maintain_parser.add_argument("--runtime-root")
    maintain_parser.add_argument("--vacuum", action="store_true")
    maintain_parser.add_argument("--no-analyze", action="store_true")
    maintain_parser.set_defaults(handler=_handle_maintain)
    return parser


def _load_uvicorn():
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("uvicorn is required to run article-local serve. Install the optional api dependencies.") from exc
    return uvicorn


def _handle_serve(args: argparse.Namespace) -> int:
    with root_env_scope(state_root=args.state_root, runtime_root=args.runtime_root):
        uvicorn = _load_uvicorn()
        uvicorn.run(
            "article_api.app:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=bool(args.reload),
        )
    return 0


def _handle_init(args: argparse.Namespace) -> int:
    _emit_json(
        initialize_local_workspace(
            state_root=args.state_root,
            runtime_root=args.runtime_root,
            write_env=args.write_env,
            overwrite_env=bool(args.overwrite_env),
        )
    )
    return 0


def _handle_doctor(args: argparse.Namespace) -> int:
    _emit_json(build_doctor_report(state_root=args.state_root, runtime_root=args.runtime_root))
    return 0


def _handle_preflight(args: argparse.Namespace) -> int:
    _emit_json(
        run_preflight(
            args.input,
            profile=args.profile,
            strict_profile=args.strict_profile,
        )
    )
    return 0


def _handle_normalize(args: argparse.Namespace) -> int:
    _emit_json(
        run_normalize(
            args.input,
            output_path=args.output,
            profile=args.profile,
            strict_profile=args.strict_profile,
        )
    )
    return 0


def _handle_render_verify(args: argparse.Namespace) -> int:
    _emit_json(
        run_render_verify(
            args.input,
            output_dir=args.output_dir,
            profile=args.profile,
            strict_profile=args.strict_profile,
            scopes=args.scope,
            renderer=args.renderer,
            rendered_pdf=args.rendered_pdf,
            page_images_dir=args.page_images_dir,
            workflow_mode=args.workflow_mode,
        )
    )
    return 0


def _handle_render_workflow_modes(_args: argparse.Namespace) -> int:
    _emit_json(build_render_workflow_modes())
    return 0


def _handle_profiles(_args: argparse.Namespace) -> int:
    _emit_json(build_profile_catalog())
    return 0


def _handle_backup(args: argparse.Namespace) -> int:
    _emit_json(
        create_backup_archive(
            args.output,
            state_root=args.state_root,
            runtime_root=args.runtime_root,
        )
    )
    return 0


def _handle_feedback(args: argparse.Namespace) -> int:
    _emit_json(
        create_feedback_archive(
            args.output,
            state_root=args.state_root,
            runtime_root=args.runtime_root,
        )
    )
    return 0


def _handle_restore(args: argparse.Namespace) -> int:
    _emit_json(
        restore_backup_archive(
            args.archive,
            state_root=args.state_root,
            runtime_root=args.runtime_root,
            force=bool(args.force),
        )
    )
    return 0


def _handle_maintain(args: argparse.Namespace) -> int:
    _emit_json(
        run_storage_maintenance(
            state_root=args.state_root,
            runtime_root=args.runtime_root,
            run_vacuum=bool(args.vacuum),
            run_analyze=not bool(args.no_analyze),
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


def serve_main() -> int:
    return main(["serve", *sys.argv[1:]])


def doctor_main() -> int:
    return main(["doctor", *sys.argv[1:]])


def backup_main() -> int:
    return main(["backup", *sys.argv[1:]])


def feedback_main() -> int:
    return main(["feedback", *sys.argv[1:]])


def restore_main() -> int:
    return main(["restore", *sys.argv[1:]])


def maintain_main() -> int:
    return main(["maintain", *sys.argv[1:]])


def module_main() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    module_main()
