"""Tests of parsing #SBATCH lines."""

import pytest

from firecrest_mcp.sbatch import parse_directives


@pytest.mark.parametrize(
    "line",
    [
        "#SBATCH --account=p1",
        "#SBATCH --account p1",
        "#SBATCH -A p1",
        "#SBATCH -Ap1",
        "#SBATCH --acc=p1",
        "#SBATCH -vA p1",
        "#SBATCH -WA p1",
        "  #SBATCH --account='p1'  # comment",
        "#SBATCH --time=10 --account=p1",
    ],
)
def test_account_forms(line):
    """Long, abbreviated, short, attached, bundled and quoted forms are found."""
    assert parse_directives(f"#!/bin/bash\n{line}\n") == {"account": ["p1"]}


def test_directives_after_commands_found():
    """Directives after the first command are read too, though sbatch ignores them."""
    script = "#!/bin/bash\n#SBATCH -p small\necho hi\n#SBATCH -p standard\n"
    assert parse_directives(script) == {"partition": ["small", "standard"]}


def test_all_checked_options():
    """Every checked option is found by its long name; others are skipped."""
    script = (
        "#SBATCH -A a -p p --reservation=r\n"
        "#SBATCH -D /d -o out -e err -i in\n"
        "#SBATCH --nodes=2 --time 1:00:00 -J name\n"
    )
    assert parse_directives(script) == {
        "account": ["a"],
        "partition": ["p"],
        "reservation": ["r"],
        "chdir": ["/d"],
        "output": ["out"],
        "error": ["err"],
        "input": ["in"],
    }


def test_other_option_value_not_mistaken():
    """The value attached to another short option is not read as an option."""
    assert parse_directives("#SBATCH -JAp\n") == {}


def test_non_directives_ignored():
    """Comments that are not #SBATCH lines are ignored."""
    assert parse_directives("# SBATCH -A x\n##SBATCH -A y\necho -A z\n") == {}


@pytest.mark.parametrize("line", ["#SBATCH -A", "#SBATCH --account 'p1"])
def test_malformed_rejected(line):
    """An option without a value or an unclosed quote is an error."""
    with pytest.raises(ValueError):
        parse_directives(line)
