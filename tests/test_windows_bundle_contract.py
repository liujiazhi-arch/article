import build_windows_local_bundle
import verify_release_artifact
import windows_bundle_smoke
import windows_bundle_contract


def test_windows_bundle_contract_is_shared_by_builder_verifier_and_smoke():
    assert windows_bundle_contract.BUNDLE_ROOT_NAME == "论文格式检查本地版"
    assert windows_bundle_contract.LAUNCHER_NAME == "启动论文格式检查.bat"
    assert windows_bundle_contract.FEEDBACK_LAUNCHER_NAME == "导出反馈包.bat"
    assert windows_bundle_contract.QUICKSTART_NAME == "快速开始.txt"
    assert windows_bundle_contract.PYTHON_ENTRY == "app/Scripts/python.exe"
    assert windows_bundle_contract.LNU_THESIS_LOCAL_ENTRY == "app/Scripts/lnu-thesis-local.exe"
    assert windows_bundle_contract.REQUIRED_SUFFIXES == (
        windows_bundle_contract.LAUNCHER_NAME,
        windows_bundle_contract.FEEDBACK_LAUNCHER_NAME,
        windows_bundle_contract.QUICKSTART_NAME,
        windows_bundle_contract.PYTHON_ENTRY,
        windows_bundle_contract.LNU_THESIS_LOCAL_ENTRY,
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
