"""src/errors.py : exceptions métier."""
from src.errors import ApiError, ConflictError, NotFoundError, ValidationError


def test_defaults():
    assert ApiError().status == 400 and ApiError().message == 'Requête invalide.'
    assert ValidationError('x').status == 400
    assert NotFoundError().status == 404 and NotFoundError().message == 'Non trouvé'
    assert ConflictError('déjà là').status == 409


def test_custom_status_and_message():
    err = ApiError('oups', status=418)
    assert err.status == 418 and err.message == 'oups' and str(err) == 'oups'


def test_hierarchy():
    for cls in (ValidationError, NotFoundError, ConflictError):
        assert issubclass(cls, ApiError)
