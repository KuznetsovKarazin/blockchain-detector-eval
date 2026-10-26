"""Saved test sources are provenance, not duplicate test modules."""
def pytest_ignore_collect(collection_path,config):
    return collection_path.is_dir() and collection_path.name.startswith('source_snapshot')
