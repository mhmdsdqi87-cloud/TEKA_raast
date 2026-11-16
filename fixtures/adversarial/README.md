# Adversarial fixture corpus — inputs designed to break RTL analyzers.

Every file here encodes a case that historically produced FALSE POSITIVES or
FALSE NEGATIVES in lexical RTL analyzers (this engine included). The scan
results are pinned by tests/test_adversarial.py: any behavior change on these
files must be a deliberate, documented decision — never an accident.

Honesty note: these fixtures are pinned to CURRENT engine behavior that was
hand-verified case by case. They are regression anchors, not proof of
correctness on inputs not present here.
