import build_windows_local_bundle
import verify_release_artifact
import windows_bundle_smoke
import windows_bundle_contract


def test_windows_bundle_contract_is_shared_by_builder_verifier_and_smoke():
    assert windows_bundle_contract.BUNDLE_ROOT_NAME == "论文格式检查本地版"
    assert windows_bundle_contract.LAUNCHER_NAME == "启动论文格式检查.bat"
    assert windows_bundle_contract.FEEDBACK_LAUNCHER_NAME == "导出反馈包.bat"
    assert windows_bundle_contract.QUICKSTART_NAME == "快速开始.txt"
    assert windows_bundle_contract.PYTHON_ENTRY == "app/python.exe"
    assert windows_bundle_contract.PYTHON_ABI_DLL_ENTRY == "app/python3.dll"
    assert windows_bundle_contract.PYTHON_DLL_ENTRY == "app/python311.dll"
    assert windows_bundle_contract.PYTHON_STDLIB_ENTRY == "app/python311.zip"
    assert windows_bundle_contract.PYTHON_PATH_ENTRY == "app/python311._pth"
    assert windows_bundle_contract.REQUIRED_SUFFIXES == (
        windows_bundle_contract.LAUNCHER_NAME,
        windows_bundle_contract.FEEDBACK_LAUNCHER_NAME,
        windows_bundle_contract.QUICKSTART_NAME,
        windows_bundle_contract.PYTHON_ENTRY,
        windows_bundle_contract.PYTHON_ABI_DLL_ENTRY,
        windows_bundle_contract.PYTHON_DLL_ENTRY,
        windows_bundle_contract.PYTHON_STDLIB_ENTRY,
        windows_bundle_contract.PYTHON_PATH_ENTRY,
        windows_bundle_contract.PYTHON_VCRUNTIME_ENTRY,
        windows_bundle_contract.PYTHON_VCRUNTIME_1_ENTRY,
        windows_bundle_contract.PYTHON_LICENSE_ENTRY,
        "data/state/.keep",
        "data/runtime/.keep",
    )

    assert build_windows_local_bundle.DEFAULT_BUNDLE_NAME == windows_bundle_contract.BUNDLE_ROOT_NAME
    assert build_windows_local_bundle.LAUNCHER_NAME == windows_bundle_contract.LAUNCHER_NAME
    assert build_windows_local_bundle.FEEDBACK_LAUNCHER_NAME == windows_bundle_contract.FEEDBACK_LAUNCHER_NAME
    assert build_windows_local_bundle.QUICKSTART_NAME == windows_bundle_contract.QUICKSTART_NAME
    assert verify_release_artifact.EXPECTED_BUNDLE_ROOT == windows_bundle_contract.BUNDLE_ROOT_NAME
    assert verify_release_artifact.REQUIRED_SUFFIXES == windows_bundle_contract.REQUIRED_SUFFIXES
    assert windows_bundle_smoke.BUNDLE_PYTHON_ENTRY == windows_bundle_contract.PYTHON_ENTRY


def test_windows_bundle_python_path_contract_rejects_build_machine_paths():
    valid = "python311.zip\n.\nLib\\site-packages\nimport site\n"
    absolute = valid + "C:\\hostedtoolcache\\windows\\Python\n"
    drive_relative = valid + "C:hostedtoolcache\\windows\\Python\n"

    assert windows_bundle_contract.is_portable_python_path_text(valid) is True
    assert windows_bundle_contract.is_portable_python_path_text(absolute) is False
    assert windows_bundle_contract.is_portable_python_path_text(drive_relative) is False
