from pathlib import Path

from doc_agent.users import TOKEN_MASK, UserConfig, UserManager


def test_user_manager_masks_and_encrypts_tokens(tmp_path: Path) -> None:
    manager = UserManager(tmp_path / "users")
    created = manager.create_user(
        UserConfig(
            user_name="测试用户",
            nga_endpoint="http://example.test/v1",
            auth_token="plain-secret-token",
        )
    )

    stored = (tmp_path / "users" / f"{created.user_id}.json").read_text(encoding="utf-8")
    assert "plain-secret-token" not in stored
    assert created.auth_token == TOKEN_MASK

    listed = manager.list_users()
    assert listed[0].auth_token == TOKEN_MASK

    public_user = manager.get_user(created.user_id)
    assert public_user is not None
    assert public_user.auth_token == TOKEN_MASK

    runtime_user = manager.get_user(created.user_id, include_secret=True)
    assert runtime_user is not None
    assert runtime_user.auth_token == "plain-secret-token"


def test_user_manager_updates_switches_and_deletes_users(tmp_path: Path) -> None:
    manager = UserManager(tmp_path / "users")
    created = manager.create_user(
        UserConfig(user_name="旧名称", nga_endpoint="http://example.test/v1", auth_token="token")
    )

    updated = manager.update_user(created.user_id, {"user_name": "新名称"})
    assert updated.user_name == "新名称"
    assert updated.auth_token == TOKEN_MASK

    current = manager.switch_user(created.user_id)
    assert current.user_id == created.user_id
    assert manager.get_current_user() is not None

    assert manager.delete_user(created.user_id) is True
    assert manager.get_user(created.user_id) is None
