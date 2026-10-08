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
// extra: { label, choices } — label is the plain-language name shown in the UI;
// choices turns the value box into a dropdown ([{value,label}] or ["a","b"]).
function O(flag, long, takesValue, modes, desc, example = "", group = "", extra = {}) {
  return { flag, long, takes_value: takesValue, modes, desc, example, group,
    label: extra.label || "", choices: extra.choices || null };
}

const OPTIONS = [
  O("-r", "--rules-file", true, new Set([0]),
    "Mutate each dictionary word with a rule file (e.g. append digits, capitalize). Stackable: pass several -r to chain rule files.",
    "-r rules/best64.rule", "Word mangling", { label: "Apply a rule file" }),
  O("-g", "--generate-rules", true, new Set([0]),
    "Generate N random mutation rules on the fly instead of a rule file.", "-g 10000", "Word mangling",
    { label: "Random rules (how many)" }),
  O("-j", "--rule-left", true, new Set([1]),
    "Apply a single rule to each word from the LEFT list (combinator only).", "-j 'c'", "Word mangling",
    { label: "Rule for the left list" }),
  O("-k", "--rule-right", true, new Set([1]),
    "Apply a single rule to each word from the RIGHT list (combinator only).", "-k '$!'", "Word mangling",
    { label: "Rule for the right list" }),

  O("-1", "--custom-charset1", true, new Set([3, 6, 7]),
    "Define custom charset ?1 for masks (e.g. -1 ?l?d = lowercase+digits).", "-1 ?l?d", "Mask character sets",
    { label: "Custom set ?1" }),
  O("-2", "--custom-charset2", true, new Set([3, 6, 7]), "Define custom charset ?2 for masks.", "-2 ?u?l", "Mask character sets",
    { label: "Custom set ?2" }),
  O("-3", "--custom-charset3", true, new Set([3, 6, 7]), "Define custom charset ?3 for masks.", "", "Mask character sets",
    { label: "Custom set ?3" }),
  O("-4", "--custom-charset4", true, new Set([3, 6, 7]), "Define custom charset ?4 for masks.", "", "Mask character sets",
    { label: "Custom set ?4" }),
  O("-i", "--increment", false, new Set([3, 6, 7]),
    "Incremental mode: try shorter lengths first, growing up to the mask.", "-i", "Password length",
    { label: "Try shorter lengths first" }),
  O("", "--increment-min", true, new Set([3, 6, 7]), "Lowest length to try in incremental mode.", "--increment-min 4", "Password length",
    { label: "Shortest length" }),
  O("", "--increment-max", true, new Set([3, 6, 7]), "Highest length to try in incremental mode.", "--increment-max 8", "Password length",
    { label: "Longest length" }),

  O("-t", "--markov-threshold", true, new Set([3, 6, 7]),
    "Statistically order mask guesses so likely characters come first.", "-t 256", "Smart ordering",
    { label: "Likely-first strength" }),
  O("", "--markov-disable", false, new Set([3, 6, 7]), "Turn off Markov ordering (pure left-to-right).", "", "Smart ordering",
    { label: "Turn off smart ordering" }),
  O("", "--markov-hcstat2", true, new Set([3, 6, 7]), "Use a custom Markov statistics file.", "", "Smart ordering",
    { label: "Custom stats file" }),

  O("-O", "--optimized-kernel-enable", false, ALL,
    "Use optimized kernels: much faster, but caps password length (usually <=31). Turn off for very long candidates.", "-O", "Speed & hardware",
    { label: "Fast mode (passwords up to ~31 chars)" }),
  O("-w", "--workload-profile", true, ALL,
    "How hard to push the hardware: 1=low/desktop-friendly, 2=default, 3=high, 4=nightmare (max, unresponsive machine).", "-w 3", "Speed & hardware",
    { label: "How hard to push the hardware", choices: [
      { value: "1", label: "1 — Low (keep the desktop usable)" },
      { value: "2", label: "2 — Default" },
      { value: "3", label: "3 — High" },
      { value: "4", label: "4 — Nightmare (machine unresponsive)" },
    ] }),
  O("-S", "--slow-candidates", false, ALL,
    "Generate candidates on CPU: slower throughput but needed for some huge rule/keyspace combos.", "-S", "Speed & hardware",
    { label: "Slow-candidate mode (huge rule sets)" }),
  O("-d", "--backend-devices", true, ALL, "Pick which GPU/CPU devices to use by id (comma-separated).", "-d 1", "Speed & hardware",
    { label: "Use only these device ids" }),
  O("-D", "--backend-device-types", true, ALL, "Restrict to device TYPES: 1=CPU, 2=GPU, 3=FPGA.", "-D 2", "Speed & hardware",
    { label: "Limit to device type", choices: [
      { value: "1", label: "CPU only" },
      { value: "2", label: "GPU only" },
      { value: "3", label: "FPGA only" },
    ] }),

  O("", "--force", false, ALL, "Ignore hardware warnings and run anyway (use sparingly).", "", "Advanced",
    { label: "Ignore hardware warnings" }),
  O("", "--session", true, ALL, "Name this session so you can pause and --restore it later.", "--session wifi1", "Advanced",
    { label: "Session name (to resume later)" }),
  O("", "--restore", false, ALL, "Resume a previously interrupted session by name.", "--restore", "Advanced",
    { label: "Resume the named session" }),
  O("", "--remove", false, ALL, "Remove cracked hashes from the hash file as they're found.", "", "Advanced",
    { label: "Strip cracked hashes from the file" }),
  O("", "--loopback", false, new Set([0]), "Feed newly cracked passwords back as candidates (with rules).", "", "Advanced",
    { label: "Feed cracked words back in" }),
  O("", "--potfile-disable", false, ALL, "Don't read or write the potfile for this run.", "", "Output",
    { label: "Ignore the potfile this run" }),
  O("-o", "--outfile", true, ALL, "Write cracked results to this file.", "-o cracked.txt", "Output",
    { label: "Save results to file" }),
  O("", "--outfile-format", true, ALL, "Format of the outfile (2 = plain password only).", "--outfile-format 2", "Output",
    { label: "Results file format", choices: [
      { value: "2", label: "Password only" },
      { value: "1", label: "Hash only" },
      { value: "3", label: "Hash + password" },
      { value: "5", label: "Hash + password + crack time" },
    ] }),
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
