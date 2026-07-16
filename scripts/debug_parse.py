import re

def _is_alcian_word(token):
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z'-]*", token))

with open('../Alician(1).txt', 'r', encoding='utf-8') as f:
    content = f.read()

raw_lines = content.strip().splitlines()
pairs = []
i = 0
while i < len(raw_lines):
    line = raw_lines[i].strip()
    if not line:
        i += 1
        continue
    tokens = line.split()
    if tokens and _is_alcian_word(tokens[0]):
        alcian = line.strip()
        i += 1
        chinese = ''
        if i < len(raw_lines):
            next_line = raw_lines[i].strip()
            if next_line and next_line.split():
                nt = next_line.split()[0]
                if not _is_alcian_word(nt):
                    chinese = next_line
                    i += 1
        pairs.append((alcian, chinese))
    else:
        i += 1

print(f'Total pairs: {len(pairs)}')
print('First 20:')
for a, c in pairs[:20]:
    print(f'  AL: [{a}]')
    print(f'  ZH: [{c}]')
    print()

empty_zh = sum(1 for a, c in pairs if not c)
print(f'Empty Chinese: {empty_zh}/{len(pairs)}')
print(f'Non-empty Chinese: {len(pairs) - empty_zh}')
