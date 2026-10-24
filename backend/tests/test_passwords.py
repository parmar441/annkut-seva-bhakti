import pytest

from app.auth.passwords import hash_password, is_common_password, password_problems, verify_password


def test_strong_password_passes():
    assert password_problems("Seva-Kitchen-42!") == []


@pytest.mark.parametrize(
    "pw,fragment",
    [
        ("Short1!a", "12 characters"),
        ("alllowercase123!", "uppercase and lowercase"),
        ("ALLUPPERCASE123!", "uppercase and lowercase"),
        ("NoDigitsHere!!ab", "number"),
        ("NoSpecialChars123", "special character"),
    ],
)
def test_policy_rules(pw, fragment):
    assert any(fragment in p for p in password_problems(pw))


@pytest.mark.parametrize("pw", ["Password1234!", "Welcome@2024!!", "P@ssw0rd12345!", "Swaminarayan#108", "Qwertyuiop123!"])
def test_common_passwords_rejected_even_with_decoration(pw):
    assert is_common_password(pw)
    assert any("too common" in p for p in password_problems(pw))


def test_uncommon_password_not_flagged():
    assert not is_common_password("Correct-Horse-Battery-9")


def test_username_inside_password_rejected():
    assert any("username" in p for p in password_problems("xAnjali.P-2026!", "anjali.p"))


def test_argon2id_hash_and_verify():
    h = hash_password("Seva-Kitchen-42!")
    assert h.startswith("$argon2id$")
    assert "Seva-Kitchen-42!" not in h
    assert verify_password("Seva-Kitchen-42!", h)
    assert not verify_password("seva-kitchen-42!", h)
    assert not verify_password("anything", "not-a-hash")
