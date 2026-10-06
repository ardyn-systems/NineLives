#!/usr/bin/env python3
"""
HashBench option-compatibility engine.

Encodes hashcat's attack modes and which options legally stack with each one,
with plain-English explanations. The GUI uses this to enable only the options
that make sense for the selected attack mode, so you never have to guess which
flags combine.

hashcat's live `--help` (parsed in hashcat_iface) enriches the descriptions and
adds any new modes/options; this module supplies the *relationships* between
them, which `--help` does not express.
"""

# Each attack mode: the -a value, a short name, what it does, and the inputs it
# consumes (so the GUI knows whether to show wordlist pickers, a mask box, etc.)
ATTACK_MODES = [
    {
        "id": 0, "name": "Straight (dictionary)",
        "inputs": ["wordlist"],   # one or more wordlists, tried in order
        "desc": "Try every word in your wordlist(s), optionally mutated by rules. "
                "The most common attack. Start here.",
    },
    {
        "id": 1, "name": "Combinator",
        "inputs": ["wordlist", "wordlist2"],
        "desc": "Concatenate every word in list A with every word in list B "
                "(e.g. 'spring' + '2024'). Good for passphrase-style targets.",
    },
    {
        "id": 3, "name": "Brute-force / Mask",
        "inputs": ["mask"],
        "desc": "Try every candidate matching a mask/charset pattern "
                "(e.g. ?d?d?d?d?d?d?d?d = all 8-digit numbers). No wordlist.",
    },
    {
        "id": 6, "name": "Hybrid: Wordlist + Mask",
        "inputs": ["wordlist", "mask"],
        "desc": "Append a mask to each word (e.g. 'password' + ?d?d?d?d). "
                "Catches 'word then digits' patterns.",
    },
    {
        "id": 7, "name": "Hybrid: Mask + Wordlist",
        "inputs": ["mask", "wordlist"],
        "desc": "Prepend a mask to each word (e.g. ?d?d?d?d + 'password'). "
                "Catches 'digits then word' patterns.",
    },
    {
        "id": 9, "name": "Association",
        "inputs": ["wordlist"],
        "desc": "Advanced: pair each hash with a specific hint word (1:1), e.g. "
                "usernames or hints. Needs a wordlist aligned to the hash file.",
    },
]

ATTACK_BY_ID = {m["id"]: m for m in ATTACK_MODES}


class Opt:
    """A hashcat option plus the attack modes it legally combines with."""

    def __init__(self, flag, long, takes_value, modes, desc, example="", group=""):
        self.flag = flag            # short flag, e.g. "-r" ("" if none)
        self.long = long            # long flag, e.g. "--rules-file"
        self.takes_value = takes_value
        self.modes = modes          # set of attack-mode ids, or "all"
        self.desc = desc
        self.example = example
        self.group = group

    def applies_to(self, attack_id):
        return self.modes == "all" or attack_id in self.modes

    def key(self):
        return self.long or self.flag


ALL = "all"

# --------------------------------------------------------------------------- #
# The option catalog, grouped for the UI. `modes` expresses stackability.
# --------------------------------------------------------------------------- #
OPTIONS = [
    # --- Rules: only straight (0). Combinator uses -j/-k instead. ----------
    Opt("-r", "--rules-file", True, {0},
        "Mutate each dictionary word with a rule file (e.g. append digits, "
        "capitalize). Stackable: pass several -r to chain rule files.",
        "-r rules/best64.rule", "Mangling (dictionary only)"),
    Opt("-g", "--generate-rules", True, {0},
        "Generate N random mutation rules on the fly instead of a rule file.",
        "-g 10000", "Mangling (dictionary only)"),
    Opt("-j", "--rule-left", True, {1},
        "Apply a single rule to each word from the LEFT list (combinator only).",
        "-j 'c'", "Mangling (combinator only)"),
    Opt("-k", "--rule-right", True, {1},
        "Apply a single rule to each word from the RIGHT list (combinator only).",
        "-k '$!'", "Mangling (combinator only)"),

    # --- Custom charsets + increment: mask-based modes only (3,6,7) --------
    Opt("-1", "--custom-charset1", True, {3, 6, 7},
        "Define custom charset ?1 for masks (e.g. -1 ?l?d = lowercase+digits).",
        "-1 ?l?d", "Mask charsets"),
    Opt("-2", "--custom-charset2", True, {3, 6, 7},
        "Define custom charset ?2 for masks.", "-2 ?u?l", "Mask charsets"),
    Opt("-3", "--custom-charset3", True, {3, 6, 7},
        "Define custom charset ?3 for masks.", "", "Mask charsets"),
    Opt("-4", "--custom-charset4", True, {3, 6, 7},
        "Define custom charset ?4 for masks.", "", "Mask charsets"),
    Opt("-i", "--increment", False, {3, 6, 7},
        "Incremental mode: try shorter lengths first, growing up to the mask.",
        "-i", "Mask length"),
    Opt("", "--increment-min", True, {3, 6, 7},
        "Lowest length to try in incremental mode.", "--increment-min 4",
        "Mask length"),
    Opt("", "--increment-max", True, {3, 6, 7},
        "Highest length to try in incremental mode.", "--increment-max 8",
        "Mask length"),

    # --- Markov (statistical ordering): helps mask modes -------------------
    Opt("-t", "--markov-threshold", True, {3, 6, 7},
        "Statistically order mask guesses so likely characters come first.",
        "-t 256", "Markov (mask tuning)"),
    Opt("", "--markov-disable", False, {3, 6, 7},
        "Turn off Markov ordering (pure left-to-right).", "", "Markov (mask tuning)"),
    Opt("", "--markov-hcstat2", True, {3, 6, 7},
        "Use a custom Markov statistics file.", "", "Markov (mask tuning)"),

    # --- Universal performance / control: valid in every mode --------------
    Opt("-O", "--optimized-kernel-enable", False, ALL,
        "Use optimized kernels: much faster, but caps password length "
        "(usually <=31). Turn off for very long candidates.",
        "-O", "Performance"),
    Opt("-w", "--workload-profile", True, ALL,
        "How hard to push the hardware: 1=low/desktop-friendly, 2=default, "
        "3=high, 4=nightmare (max, unresponsive machine).",
        "-w 3", "Performance"),
    Opt("-S", "--slow-candidates", False, ALL,
        "Generate candidates on CPU: slower throughput but needed for some "
        "huge rule/keyspace combos.", "-S", "Performance"),
    Opt("-d", "--backend-devices", True, ALL,
        "Pick which GPU/CPU devices to use by id (comma-separated).",
        "-d 1", "Performance"),
    Opt("-D", "--backend-device-types", True, ALL,
        "Restrict to device TYPES: 1=CPU, 2=GPU, 3=FPGA.", "-D 2", "Performance"),

    Opt("", "--force", False, ALL,
        "Ignore hardware warnings and run anyway (use sparingly).", "",
        "Control"),
    Opt("", "--status", False, ALL,
        "Print a periodic status screen while running.", "", "Control"),
    Opt("", "--status-timer", True, ALL,
        "Seconds between status updates.", "--status-timer 10", "Control"),
    Opt("", "--session", True, ALL,
        "Name this session so you can pause and --restore it later.",
        "--session wifi1", "Control"),
    Opt("", "--restore", False, ALL,
        "Resume a previously interrupted session by name.", "--restore",
        "Control"),
    Opt("", "--remove", False, ALL,
        "Remove cracked hashes from the hash file as they're found.", "",
        "Control"),
    Opt("", "--loopback", False, {0},
        "Feed newly cracked passwords back as candidates (with rules).", "",
        "Control"),
    Opt("", "--potfile-disable", False, ALL,
        "Don't read or write the potfile for this run.", "", "Output"),
    Opt("-o", "--outfile", True, ALL,
        "Write cracked results to this file.", "-o cracked.txt", "Output"),
    Opt("", "--outfile-format", True, ALL,
        "Format of the outfile (2 = plain password only).", "--outfile-format 2",
        "Output"),
]


def options_for(attack_id):
    """All options that legally stack with the given attack mode."""
    return [o for o in OPTIONS if o.applies_to(attack_id)]


def grouped_options_for(attack_id):
    """Options for a mode, bucketed by UI group, preserving catalog order."""
    groups = {}
    for o in options_for(attack_id):
        groups.setdefault(o.group, []).append(o)
    return groups


def inputs_for(attack_id):
    """Which input widgets the UI should show for this mode."""
    return ATTACK_BY_ID.get(attack_id, {}).get("inputs", [])


def explain_mode(attack_id):
    m = ATTACK_BY_ID.get(attack_id)
    return m["desc"] if m else ""


if __name__ == "__main__":
    # Quick human-readable dump of the stackability matrix.
    for m in ATTACK_MODES:
        print(f"\n=== -a {m['id']}  {m['name']} ===")
        print(f"   inputs: {', '.join(m['inputs'])}")
        print(f"   {m['desc']}")
        for grp, opts in grouped_options_for(m["id"]).items():
            print(f"   [{grp}]")
            for o in opts:
                print(f"      {o.flag or '  '} {o.long:<26} {o.desc[:60]}")
