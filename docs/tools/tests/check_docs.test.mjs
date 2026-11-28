import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const checker = fileURLToPath(new URL('../check_docs.mjs', import.meta.url));
const metadata = [
  '---', 'title: Fixture', 'created_date: 2026-11-21', 'update_date: 2026-11-21',
  'status: APPROVED', 'tags: [fixture, handbook]', '---', '',
].join('\n');

function makeFixture(t, content, extraFile) {
  const root = mkdtempSync(join(tmpdir(), 'koios-check-docs-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  mkdirSync(join(root, 'docs'));
  writeFileSync(join(root, 'AGENTS.md'), `${metadata}# Entry\n`);
  writeFileSync(join(root, 'docs', 'README.md'), content);
  writeFileSync(join(root, 'docs', 'Target.md'), `${metadata}# Target\n\n## Details\n\n## Details\n`);
  if (extraFile) writeFileSync(join(root, 'docs', extraFile), 'fixture');
  return root;
}

function runChecker(root) {
  const result = spawnSync(process.execPath, [checker, root], { encoding: 'utf8' });
  assert.ifError(result.error);
  assert.equal(result.signal, null);
  return result;
}

function check(t, content, extraFile) {
  return runChecker(makeFixture(t, content, extraFile));
}

function passes(result) {
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /^PASS: 3 Markdown files;/);
}

test('valid local link to target heading passes', t => {
  passes(check(t, `${metadata}# Handbook\n\n[Details](Target.md#details)\n`));
});

test('automatic duplicate-heading suffix resolves', t => {
  passes(check(t, `${metadata}# Handbook\n\n[Second details](Target.md#details-1)\n`));
});

test('fenced example links and headings are ignored', t => {
  const fence = '`'.repeat(3);
  const body = ['# Handbook', '', `${fence}md`, '#### Not a heading',
    '[Not a link](absent.md)', fence, ''].join('\n');
  passes(check(t, metadata + body));
});

const bad = [
  ['missing target', metadata, '\n[Link](absent.md)\n', /missing link target: absent\.md/],
  ['missing fragment', metadata, '\n[Link](Target.md#absent)\n', /missing heading\/anchor: Target\.md#absent/],
  ['heading jump', metadata, '\n### Out of order\n', /heading level jumps from 1 to 3/],
  ['missing metadata field', metadata.replace('status: APPROVED\n', ''), '', /missing metadata field: status/],
  ['invalid metadata date', metadata.replace('2026-11-21', '2026-02-30'), '', /invalid date: created_date/],
  ['missing front matter', '', '', /missing front matter/],
  ['repository escape', metadata, '\n[Outside](../../outside.md)\n', /link escapes repository: \.\.\/\.\.\/outside\.md/],
  ['explicit anchor before heading', metadata, '\n<a id="section"></a>\n## Section\n', /explicit anchor duplicates heading ID: section/],
  ['explicit anchor after heading', metadata, '\n## Section\n<a name="section"></a>\n', /explicit anchor duplicates heading ID: section/],
];

for (const [name, header, body, diagnostic] of bad) {
  test(`${name} fails with a diagnostic`, t => {
    const result = check(t, `${header}# Handbook\n${body}`);
    assert.equal(result.status, 1, result.stdout || result.stderr);
    assert.match(result.stderr, /docs\/README\.md:/);
    assert.match(result.stderr, diagnostic);
  });
};

test('literal inline code links are ignored', t => {
  const lines = [
    '# Handbook',
    'Literal example: `[Example](does-not-exist.md)`.',
    '`[First](first.md)` and `` ` [Second](second.md) ``.',
    '`` `[Exact match](exact.md)` ``` ``',
    '[`Code label`](Target.md#details)',
    '',
  ];
  passes(check(t, metadata + lines.join('\n')));
});

const visibleLinks = [
  ['after closed code', '`[Hidden](hidden.md)` [Visible](visible.md)',
    /missing link target: visible\.md/],
  ['after unmatched delimiter', '` no closing delimiter [Visible](Target.md#absent)',
    /missing heading\/anchor: Target\.md#absent/],
  ['after unmatched longer delimiter', '`` unmatched `[Hidden](hidden.md)` [Visible](visible.md)',
    /missing link target: visible\.md/],
  ['after escaped delimiter', '\\` [Visible](visible.md) `',
    /missing link target: visible\.md/],
];

for (const [name, line, diagnostic] of visibleLinks) {
  test(`rendered link ${name} still fails validation`, t => {
    const result = check(t, `${metadata}# Handbook\n\n${line}\n`);
    assert.equal(result.status, 1, result.stdout || result.stderr);
    assert.match(result.stderr, /docs\/README\.md:/);
    assert.match(result.stderr, diagnostic);
    assert.doesNotMatch(result.stderr, /missing link target: hidden\.md/);
  });
};

test('literal backticks in ordinary and angle-bracket destinations preserve valid links', t => {
  const lines = [
    '# Handbook',
    '[Ordinary](target`file`.txt)',
    '[Angle](<target`file`.txt>)',
    '[`Code with ] inside`](Target.md#details)',
    '',
  ];
  const result = check(t, metadata + lines.join('\n'), 'target`file`.txt');
  passes(result);
  assert.match(result.stdout, /3 local links checked/);
});

const rawDestinations = [
  ['ordinary missing', 'missing`file`.md', /missing link target: missing`file`\.md/],
  ['angle-bracket missing', '<missing`file`.md>', /missing link target: missing`file`\.md/],
  ['ordinary escape', '../../outside`file`.md', /link escapes repository: \.\.\/\.\.\/outside`file`\.md/],
  ['angle-bracket escape', '<../../outside`file`.md>', /link escapes repository: \.\.\/\.\.\/outside`file`\.md/],
];

for (const [name, destination, diagnostic] of rawDestinations) {
  test(`${name} destination keeps literal backticks`, t => {
    const result = check(t, `${metadata}# Handbook\n\n[\`Code label\`](${destination})\n`);
    assert.equal(result.status, 1, result.stdout || result.stderr);
    assert.match(result.stderr, /^docs\/README\.md:/);
    assert.match(result.stderr, diagnostic);
  });
};

test('local links require exact filename and directory spelling', t => {
  const root = makeFixture(t, `${metadata}# Handbook\n`);
  const docs = join(root, 'docs');
  mkdirSync(join(docs, 'Section'));
  writeFileSync(join(docs, 'Section', 'Link Target.md'), `${metadata}# Target\n`);
  const fileAlias = existsSync(join(docs, 'Section', 'link Target.md'));
  const directoryAlias = existsSync(join(docs, 'section', 'Link Target.md'));
  t.diagnostic(`platform=${process.platform}; native wrong-case filename lookup=${fileAlias}; directory lookup=${directoryAlias}`);
  const source = join(docs, 'README.md');
  const cases = [
    ['../docs/./Section/Link%20Target.md#target', 0, null],
    ['Section/Absent.md', 1, /missing link target: Section\/Absent\.md/],
    ['Section/link%20Target.md#target', 1, fileAlias ? /link path casing differs/ : /missing link target/],
    ['section/Link%20Target.md#target', 1, directoryAlias ? /link path casing differs/ : /missing link target/],
  ];
  const results = cases.map(([link, status, diagnostic]) => {
    writeFileSync(source, `${metadata}# Handbook\n\n[Link](${link})\n`);
    const result = runChecker(root);
    t.diagnostic(`${link}: checker exit=${result.status}`);
    return { link, status, diagnostic, result };
  });
  for (const { link, status, diagnostic, result } of results) {
    assert.equal(result.status, status, link);
    if (diagnostic) {
      assert.match(result.stderr, /^docs\/README\.md:/);
      assert.match(result.stderr, diagnostic);
      assert.ok(result.stderr.includes(link), result.stderr);
    } else {
      assert.match(result.stdout, /1 local links checked/);
    }
  }
});
