from src.utils.urn import generate_urn, is_valid_urn, normalize_asset_path, parse_urn


def test_generate_urn() -> None:
    urn = generate_urn("dataset", "finance_repo", "prod_db.dim_users")
    assert urn == "urn:li:dataset:finance_repo:prod_db.dim_users"


def test_parse_urn_roundtrip() -> None:
    urn = "urn:li:file:etl_service:src/transform.py"
    parts = parse_urn(urn)
    assert parts["entity_type"] == "file"
    assert parts["project_id"] == "etl_service"
    assert parts["asset_path"] == "src/transform.py"


def test_normalize_asset_path() -> None:
    path = r"C:\repo\project\src\job.py"
    normalized = normalize_asset_path(path)
    assert normalized == "C/repo/project/src/job.py"


def test_is_valid_urn() -> None:
    assert is_valid_urn("urn:li:dataset:project:db.table")
    assert not is_valid_urn("urn:foo:dataset:project:db.table")
