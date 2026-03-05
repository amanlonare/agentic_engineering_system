
import sys
# Absolute import from repo root
from myapp.logic import get_val

# Full path file access
with open('.context/test-path-repo/sample.txt') as f:
    content = f.read()

assert 'HELLO_WORLD' in content
assert get_val() == 'ROCK_ON'
print("ALL_SYSTEMS_GO")
