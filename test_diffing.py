import pytest
from automation.diffing import filter_unmanaged


def test_filter_unmanaged_removes_exemptions():
    """Filtering removes exempted lines and keeps non-exempted ones."""
    unmanaged = [" shutdown", " snmp-server community public RO", " description core"]
    exceptions = {"interfaces": {" shutdown", " description core"}}

    result = filter_unmanaged(
        unmanaged_lines=unmanaged, exceptions=exceptions, section="interfaces"
    )

    assert result == [" snmp-server community public RO"]


def test_filter_unmanaged_preserves_order():
    """Filtering preserves the exact CLI line order of remaining items."""
    unmanaged = [" line 1", " line 2", " line 3", " line 4"]
    exceptions = {"ntp": {" line 2"}}

    result = filter_unmanaged(
        unmanaged_lines=unmanaged, exceptions=exceptions, section="ntp"
    )

    assert result == [" line 1", " line 3", " line 4"]


def test_filter_unmanaged_empty_input():
    """Returns an empty list when unmanaged_lines is empty."""
    exceptions = {"interfaces": {" shutdown"}}

    result = filter_unmanaged(
        unmanaged_lines=[], exceptions=exceptions, section="interfaces"
    )

    assert result == []


def test_filter_unmanaged_missing_section():
    """Returns all unmanaged lines if the section key is not in exceptions."""
    unmanaged = [" shutdown"]
    exceptions = {"ntp": {" ntp server 10.0.0.1"}}

    result = filter_unmanaged(
        unmanaged_lines=unmanaged, exceptions=exceptions, section="interfaces"
    )

    assert result == [" shutdown"]


def test_filter_unmanaged_all_exempted():
    """Returns an empty list when all unmanaged lines are exempted."""
    unmanaged = [" shutdown", " description core"]
    exceptions = {"interfaces": {" shutdown", " description core"}}

    result = filter_unmanaged(
        unmanaged_lines=unmanaged, exceptions=exceptions, section="interfaces"
    )

    assert result == []
