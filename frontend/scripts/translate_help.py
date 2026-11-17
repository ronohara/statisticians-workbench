"""
Script to help translate YAML locale files.
Reads the English source and an existing translated file,
identifies missing keys, and prints them for manual translation.
"""
import yaml
import sys

if len(sys.argv) < 3:
    print("Usage: python translate_help.py <en.yaml> <target.yaml>")
    sys.exit(1)

with open(sys.argv[1]) as f:
    en = yaml.safe_load(f)

with open(sys.argv[2]) as f:
    target = yaml.safe_load(f)

en_keys = set(en.keys())
target_keys = set(target.keys())

missing = en_keys - target_keys
extra = target_keys - en_keys

print(f"English keys: {len(en_keys)}")
print(f"Target keys: {len(target_keys)}")
print(f"Missing: {len(missing)}")
print(f"Extra: {len(extra)}")

if missing:
    print("\nMissing keys:")
    for k in sorted(missing):
        print(f"  {k}: {en[k]}")
