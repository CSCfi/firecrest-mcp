"""Parsing of the job options that #SBATCH lines set, for the policy checks."""

import shlex

# The sbatch options the policy checks, with their short forms.
CHECKED_OPTIONS = {
    "account": "A",
    "partition": "p",
    "reservation": None,
    "chdir": "D",
    "output": "o",
    "error": "e",
    "input": "i",
}
SHORT_OPTIONS = {short: name for name, short in CHECKED_OPTIONS.items() if short}
# sbatch short options without an argument, which may be bundled before a checked
# one (e.g. "-vA project_1").
SHORT_FLAGS = set("hHkOQsuvVW")


def _long_option(name: str) -> str | None:
    # sbatch, like getopt_long, accepts any unambiguous prefix of a long option, so
    # "--acc" means "--account". Treating every prefix of a checked option as that
    # option may refuse an ambiguous one that sbatch would reject anyway.
    for option in CHECKED_OPTIONS:
        if option.startswith(name):
            return option
    return None


def parse_directives(script: str) -> dict[str, list[str]]:
    """Return the values of the checked options set by #SBATCH lines in a script.

    sbatch reads #SBATCH lines only until the first command, but every line that
    starts with #SBATCH is read here, so a directive can't be hidden from the check.
    Values are returned in order of appearance under the long option name; options
    that are not checked are skipped.
    """
    found: dict[str, list[str]] = {}
    for line in script.splitlines():
        line = line.strip()
        if not line.startswith("#SBATCH"):
            continue
        try:
            tokens = shlex.split(line.removeprefix("#SBATCH"), comments=True)
        except ValueError as e:
            raise ValueError(f"Could not parse {line!r}: {e}") from e
        i = 0
        while i < len(tokens):
            token = tokens[i]
            i += 1
            option, value = None, None
            if token.startswith("--"):
                name, sep, rest = token[2:].partition("=")
                option = _long_option(name) if name else None
                if sep:
                    value = rest
            elif token.startswith("-") and len(token) > 1:
                for pos, char in enumerate(token[1:], start=2):
                    if char in SHORT_OPTIONS:
                        option = SHORT_OPTIONS[char]
                        value = token[pos:] or None
                        break
                    if char not in SHORT_FLAGS:
                        # Any other option takes the rest of the token as its value.
                        break
            if option is None:
                continue
            if value is None:
                if i == len(tokens):
                    raise ValueError(f"Option in {line!r} has no value.")
                value = tokens[i]
                i += 1
            found.setdefault(option, []).append(value)
    return found
