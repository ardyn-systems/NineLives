"use strict";
/* Attack-mode ↔ stackable-option matrix — Node port of compat.py. */

const ATTACK_MODES = [
  { id: 0, name: "Straight (dictionary)", inputs: ["wordlist"],
    desc: "Try every word in your wordlist(s), optionally mutated by rules. The most common attack. Start here." },
  { id: 1, name: "Combinator", inputs: ["wordlist", "wordlist2"],
    desc: "Concatenate every word in list A with every word in list B (e.g. 'spring' + '2024'). Good for passphrase-style targets." },
  { id: 3, name: "Brute-force / Mask", inputs: ["mask"],
    desc: "Try every candidate matching a mask/charset pattern (e.g. ?d?d?d?d?d?d?d?d = all 8-digit numbers). No wordlist." },
  { id: 6, name: "Hybrid: Wordlist + Mask", inputs: ["wordlist", "mask"],
    desc: "Append a mask to each word (e.g. 'password' + ?d?d?d?d). Catches 'word then digits' patterns." },
  { id: 7, name: "Hybrid: Mask + Wordlist", inputs: ["mask", "wordlist"],
    desc: "Prepend a mask to each word (e.g. ?d?d?d?d + 'password'). Catches 'digits then word' patterns." },
  { id: 9, name: "Association", inputs: ["wordlist"],
    desc: "Advanced: pair each hash with a specific hint word (1:1), e.g. usernames or hints. Needs a wordlist aligned to the hash file." },
];
const ATTACK_BY_ID = Object.fromEntries(ATTACK_MODES.map((m) => [m.id, m]));

const ALL = "all";
// flag, long, takesValue, modes (Set or "all"), desc, example, group
function O(flag, long, takesValue, modes, desc, example = "", group = "") {
  return { flag, long, takes_value: takesValue, modes, desc, example, group };
}

const OPTIONS = [
  O("-r", "--rules-file", true, new Set([0]),
    "Mutate each dictionary word with a rule file (e.g. append digits, capitalize). Stackable: pass several -r to chain rule files.",
    "-r rules/best64.rule", "Mangling (dictionary only)"),
  O("-g", "--generate-rules", true, new Set([0]),
    "Generate N random mutation rules on the fly instead of a rule file.", "-g 10000", "Mangling (dictionary only)"),
  O("-j", "--rule-left", true, new Set([1]),
    "Apply a single rule to each word from the LEFT list (combinator only).", "-j 'c'", "Mangling (combinator only)"),
  O("-k", "--rule-right", true, new Set([1]),
    "Apply a single rule to each word from the RIGHT list (combinator only).", "-k '$!'", "Mangling (combinator only)"),

  O("-1", "--custom-charset1", true, new Set([3, 6, 7]),
    "Define custom charset ?1 for masks (e.g. -1 ?l?d = lowercase+digits).", "-1 ?l?d", "Mask charsets"),
  O("-2", "--custom-charset2", true, new Set([3, 6, 7]), "Define custom charset ?2 for masks.", "-2 ?u?l", "Mask charsets"),
  O("-3", "--custom-charset3", true, new Set([3, 6, 7]), "Define custom charset ?3 for masks.", "", "Mask charsets"),
  O("-4", "--custom-charset4", true, new Set([3, 6, 7]), "Define custom charset ?4 for masks.", "", "Mask charsets"),
  O("-i", "--increment", false, new Set([3, 6, 7]),
    "Incremental mode: try shorter lengths first, growing up to the mask.", "-i", "Mask length"),
  O("", "--increment-min", true, new Set([3, 6, 7]), "Lowest length to try in incremental mode.", "--increment-min 4", "Mask length"),
  O("", "--increment-max", true, new Set([3, 6, 7]), "Highest length to try in incremental mode.", "--increment-max 8", "Mask length"),

  O("-t", "--markov-threshold", true, new Set([3, 6, 7]),
    "Statistically order mask guesses so likely characters come first.", "-t 256", "Markov (mask tuning)"),
  O("", "--markov-disable", false, new Set([3, 6, 7]), "Turn off Markov ordering (pure left-to-right).", "", "Markov (mask tuning)"),
  O("", "--markov-hcstat2", true, new Set([3, 6, 7]), "Use a custom Markov statistics file.", "", "Markov (mask tuning)"),

  O("-O", "--optimized-kernel-enable", false, ALL,
    "Use optimized kernels: much faster, but caps password length (usually <=31). Turn off for very long candidates.", "-O", "Performance"),
  O("-w", "--workload-profile", true, ALL,
    "How hard to push the hardware: 1=low/desktop-friendly, 2=default, 3=high, 4=nightmare (max, unresponsive machine).", "-w 3", "Performance"),
  O("-S", "--slow-candidates", false, ALL,
    "Generate candidates on CPU: slower throughput but needed for some huge rule/keyspace combos.", "-S", "Performance"),
  O("-d", "--backend-devices", true, ALL, "Pick which GPU/CPU devices to use by id (comma-separated).", "-d 1", "Performance"),
  O("-D", "--backend-device-types", true, ALL, "Restrict to device TYPES: 1=CPU, 2=GPU, 3=FPGA.", "-D 2", "Performance"),

  O("", "--force", false, ALL, "Ignore hardware warnings and run anyway (use sparingly).", "", "Control"),
  O("", "--status", false, ALL, "Print a periodic status screen while running.", "", "Control"),
  O("", "--status-timer", true, ALL, "Seconds between status updates.", "--status-timer 10", "Control"),
  O("", "--session", true, ALL, "Name this session so you can pause and --restore it later.", "--session wifi1", "Control"),
  O("", "--restore", false, ALL, "Resume a previously interrupted session by name.", "--restore", "Control"),
  O("", "--remove", false, ALL, "Remove cracked hashes from the hash file as they're found.", "", "Control"),
  O("", "--loopback", false, new Set([0]), "Feed newly cracked passwords back as candidates (with rules).", "", "Control"),
  O("", "--potfile-disable", false, ALL, "Don't read or write the potfile for this run.", "", "Output"),
  O("-o", "--outfile", true, ALL, "Write cracked results to this file.", "-o cracked.txt", "Output"),
  O("", "--outfile-format", true, ALL, "Format of the outfile (2 = plain password only).", "--outfile-format 2", "Output"),
];

function appliesTo(opt, attackId) {
  return opt.modes === ALL || (opt.modes instanceof Set && opt.modes.has(attackId));
}
function optionsFor(attackId) {
  return OPTIONS.filter((o) => appliesTo(o, attackId));
}
function groupedOptionsFor(attackId) {
  const groups = new Map();
  for (const o of optionsFor(attackId)) {
    if (!groups.has(o.group)) groups.set(o.group, []);
    groups.get(o.group).push(o);
  }
  return groups;
}
function inputsFor(attackId) {
  return (ATTACK_BY_ID[attackId] && ATTACK_BY_ID[attackId].inputs) || [];
}

module.exports = { ATTACK_MODES, ATTACK_BY_ID, OPTIONS, optionsFor, groupedOptionsFor, inputsFor };
