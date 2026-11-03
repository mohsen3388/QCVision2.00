from visionqc.security.repository import hash_password
from visionqc.security.models import Session

def test_password_hash_is_salted_and_repeatable():
    salt,digest=hash_password('secret')
    _,again=hash_password('secret',bytes.fromhex(salt))
    assert digest==again
    assert digest!='secret'

def test_rbac_permissions():
    assert Session('a','A','Administrator').can('anything')
    assert Session('q','Q','QC Manager').can('quality.configure')
    assert not Session('o','O','Operator').can('quality.configure')
