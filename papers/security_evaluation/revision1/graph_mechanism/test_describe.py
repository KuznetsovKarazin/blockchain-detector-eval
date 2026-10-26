from describe_mechanism import declaration_heuristics

def test_comments_and_literals_do_not_create_declarations():
    s='// library Fake {}\ncontract C { string x="interface Nope {}"; /* library Bad{} */ }'
    d=declaration_heuristics(s,'C.sol')
    assert d['contract_declarations']==1 and d['library_declarations']==0 and d['interface_declarations']==0

def test_library_with_application_contract_is_not_library_only():
    d=declaration_heuristics('library SafeMath{} contract Vault{}','Vault.sol')
    assert d['any_library_or_interface_declaration'] and not d['exclusively_library_or_interface_declarations']

def test_interface_and_standard_filename_are_separate():
    d=declaration_heuristics('interface IFoo{}','custom.sol')
    assert d['exclusively_library_or_interface_declarations'] and not d['known_utility_or_standard_filename']
