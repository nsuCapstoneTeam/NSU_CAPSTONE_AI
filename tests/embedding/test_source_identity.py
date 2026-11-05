"""Portable source identity contract; no model, Docker or database is needed."""

import hashlib
from itertools import permutations
from pathlib import PurePosixPath, PureWindowsPath

import pytest

from app.embedding.source_identity import canonical_source_identity, package_source_files


CONTENTS = {
    '__init__.py': b'root\n',
    'A/child.py': b'child\r\n',
    'a.py': b'sibling\n',
    'configs/Config.YML': b'config\r\n',
    'models/Z.py': b'model\n',
}
EXPECTED_ORDER = ['__init__.py', 'A/child.py', 'a.py', 'configs/Config.YML', 'models/Z.py']
# Independently framed in the explicit order above, without the production helper.
EXPECTED_SHA256 = '6ba896d33c9309fdab917062cf9ba7615017c248ad49fe74c2e3e91273d62c28'


@pytest.mark.parametrize(('flavour', 'root_name'), [
    (PureWindowsPath, 'C:/Host/Lib/site-packages/msclap'),
    (PurePosixPath, '/different/host/site-packages/msclap'),
])
def test_windows_and_posix_inputs_have_same_identity_for_every_traversal_order(flavour, root_name):
    root = flavour(root_name)
    entries = [((root / name).relative_to(root), hashlib.sha256(content).hexdigest())
               for name, content in CONTENTS.items()]
    for traversal_order in permutations(entries):
        digest, files = canonical_source_identity(traversal_order)
        assert digest == EXPECTED_SHA256
        assert list(files) == EXPECTED_ORDER
    # A directory component sorts before its sibling a.py, unlike string lexical order.
    assert EXPECTED_ORDER.index('A/child.py') < EXPECTED_ORDER.index('a.py')


@pytest.mark.parametrize('flavour', [PureWindowsPath, PurePosixPath])
def test_folded_component_ties_use_original_spelling_and_no_locale(flavour):
    names = ['a.py', 'Straße.py', 'A.py', 'STRASSE.py']
    _, files = canonical_source_identity((flavour(name), 'ab' * 32) for name in names)
    assert list(files) == ['A.py', 'a.py', 'STRASSE.py', 'Straße.py']


def test_original_path_case_and_raw_content_newlines_remain_identity_inputs():
    def identity(contents):
        return canonical_source_identity(
            (PurePosixPath(name), hashlib.sha256(content).hexdigest())
            for name, content in contents.items()
        )[0]
    assert identity(CONTENTS) == EXPECTED_SHA256
    renamed = dict(CONTENTS)
    renamed['a/child.py'] = renamed.pop('A/child.py')
    assert identity(renamed) != EXPECTED_SHA256
    changed_newline = dict(CONTENTS, **{'A/child.py': b'child\n'})
    assert identity(changed_newline) != EXPECTED_SHA256


def test_filesystem_scan_keeps_existing_source_scope_and_raw_bytes(tmp_path):
    for name, content in CONTENTS.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (tmp_path / 'weights.bin').write_bytes(b'not source')
    (tmp_path / 'README.md').write_text('not source', encoding='utf-8')
    source_files = package_source_files(tmp_path)
    digest, files = canonical_source_identity(
        (path.relative_to(tmp_path), hashlib.sha256(path.read_bytes()).hexdigest())
        for path in source_files
    )
    assert digest == EXPECTED_SHA256
    assert list(files) == EXPECTED_ORDER
    assert (tmp_path / 'A/child.py').read_bytes() == b'child\r\n'


@pytest.mark.parametrize('path', [
    PurePosixPath('/absolute.py'), PureWindowsPath('C:/absolute.py'),
    PureWindowsPath('C:drive-relative.py'), PureWindowsPath('/rooted.py'),
    PurePosixPath('../parent.py'), PurePosixPath('.'),
])
def test_host_or_parent_paths_are_not_accepted_as_relative_identity(path):
    with pytest.raises(ValueError, match='root-relative'):
        canonical_source_identity([(path, 'ab' * 32)])


def test_duplicate_relative_path_is_rejected_instead_of_overwriting_identity():
    with pytest.raises(ValueError, match='duplicate'):
        canonical_source_identity([(PurePosixPath('same.py'), 'ab' * 32)] * 2)
