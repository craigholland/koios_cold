import { existsSync, lstatSync, readFileSync, readdirSync, realpathSync } from 'node:fs';
import { dirname, extname, relative, resolve, sep } from 'node:path';

function markdownFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = resolve(directory, entry.name);
    if (entry.isSymbolicLink()) throw new Error(`Symlink is outside checker scope: ${path}`);
    if (entry.isDirectory()) return markdownFiles(path);
    return entry.isFile() && extname(path) === '.md' ? [path] : [];
  });
}

function visibleLines(text) {
  let fence;
  return text.split(/\r?\n/).map(line => {
    const marker = line.match(/^ {0,3}(`{3,}|~{3,})/);
    if (fence) {
      if (marker && marker[1][0] === fence[0] && marker[1].length >= fence.length
          && line.slice(marker[0].length).trim() === '') fence = undefined;
      return '';
    }
    if (marker) {
      fence = marker[1];
      return '';
    }
    return line;
  });
}

function closingBackticks(line) {
  const runs = [...line.matchAll(/`+/g)];
  const nextByLength = new Map();
  const closing = new Map();
  for (let i = runs.length - 1; i >= 0; i--) {
    const { 0: run, index } = runs[i];
    const end = nextByLength.get(run.length);
    if (end !== undefined) closing.set(index, end);
    nextByLength.set(run.length, index + run.length);
  }
  return closing;
}

function isEscaped(line, index) {
  let before = index;
  while (before > 0 && line[before - 1] === '\\') before--;
  return (index - before) % 2 !== 0;
}

// Keep link destinations verbatim. Once a link is recognized, skip its
// destination entirely when looking for the next inline code opener.
function* linkDestinations(line) {
  const closing = closingBackticks(line);
  const starts = /`+|!?\[/g;
  const labelParts = /`+|\]/g;
  const destination = /\]\((?:<([^>]+)>|([^\s)]+))(?:\s+["'][^"']*["'])?\)/y;
  let start;
  while ((start = starts.exec(line))) {
    if (start[0][0] === '`') {
      if (!isEscaped(line, start.index)) {
        starts.lastIndex = closing.get(start.index) ?? starts.lastIndex;
      }
      continue;
    }
    labelParts.lastIndex = starts.lastIndex;
    let part;
    while ((part = labelParts.exec(line))) {
      if (part[0][0] === '`') {
        if (!isEscaped(line, part.index)) {
          labelParts.lastIndex = closing.get(part.index) ?? labelParts.lastIndex;
        }
        continue;
      }
      destination.lastIndex = part.index;
      const link = destination.exec(line);
      if (link) {
        yield link[1] ?? link[2];
        starts.lastIndex = destination.lastIndex;
      }
      break;
    }
  }
}

function headingSlug(text) {
  return text.replace(/<[^>]*>/g, '').toLowerCase()
    .replace(/[^\p{L}\p{N}\p{M}_\-\s]/gu, '').replace(/\s/g, '-');
}

class HandbookValidator {
  constructor(root) {
    this.root = realpathSync(resolve(root));
    this.documents = new Map();
    this.errors = [];
    this.linkCount = 0;
  }

  error(path, message) {
    this.errors.push(`${relative(this.root, path).split(sep).join('/')}: ${message}`);
  }

  inspect(path, requireMetadata = true) {
    if (this.documents.has(path)) return this.documents.get(path);
    if (!this.contains(realpathSync(path))) throw new Error('Document resolves outside repository root');
    const text = readFileSync(path, 'utf8');
    const metadata = text.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
    if (requireMetadata) this.checkMetadata(path, metadata?.[1]);
    const body = metadata ? text.slice(metadata[0].length) : text;
    const lines = visibleLines(body);
    const anchors = new Set();
    const headings = new Set();
    let previousLevel = 0;
    let topLevelCount = 0;

    for (const line of lines) {
      for (const explicit of line.matchAll(/<a\b[^>]*\b(?:id|name)\s*=\s*["']([^"']+)["'][^>]*>/gi)) {
        if (anchors.has(explicit[1])) this.error(path, `duplicate explicit anchor: ${explicit[1]}`);
        if (headings.has(explicit[1])) this.error(path, `explicit anchor duplicates heading ID: ${explicit[1]}`);
        anchors.add(explicit[1]);
      }
      const heading = line.match(/^(#{1,6})\s+(.+?)(?:\s+#+)?\s*$/);
      if (!heading) continue;
      const level = heading[1].length;
      if (previousLevel === 0 && level !== 1) this.error(path, 'first heading must be level 1');
      if (previousLevel && level > previousLevel + 1) this.error(path, `heading level jumps from ${previousLevel} to ${level}`);
      if (level === 1) topLevelCount++;
      previousLevel = level;
      const base = headingSlug(heading[2]);
      let slug = base;
      let suffix = 0;
      while (headings.has(slug)) slug = `${base}-${++suffix}`;
      if (anchors.has(slug)) this.error(path, `explicit anchor duplicates heading ID: ${slug}`);
      headings.add(slug);
    }
    if (topLevelCount !== 1) this.error(path, `expected one level-1 heading, found ${topLevelCount}`);
    const document = { lines, anchors: new Set([...anchors, ...headings]) };
    this.documents.set(path, document);
    return document;
  }

  checkMetadata(path, metadata) {
    if (!metadata) {
      this.error(path, 'missing front matter');
      return;
    }
    const value = name => metadata.match(new RegExp(`^${name}:\\s*(.+)$`, 'm'))?.[1].trim();
    for (const name of ['title', 'created_date', 'update_date', 'status', 'tags']) {
      if (!value(name)) this.error(path, `missing metadata field: ${name}`);
    }
    for (const name of ['created_date', 'update_date']) {
      const date = value(name);
      const parsed = Date.parse(`${date}T00:00:00Z`);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date ?? '') || !Number.isFinite(parsed)
          || new Date(parsed).toISOString().slice(0, 10) !== date) this.error(path, `invalid date: ${name}`);
    }
    if (value('update_date') < value('created_date')) this.error(path, 'update_date precedes created_date');
    if (!['DRAFT', 'APPROVED'].includes(value('status'))) this.error(path, 'status must be DRAFT or APPROVED');
    if (!/^\[[^\]]+,\s*[^\]]+\]$/.test(value('tags') ?? '')) this.error(path, 'tags must contain at least two descriptive entries');
  }

  checkLinks(path, document) {
    for (const line of document.lines) {
      for (const raw of linkDestinations(line)) {
        if (/^[a-z][a-z\d+.-]*:/i.test(raw) || raw.startsWith('//')) continue;
        this.linkCount++;
        try {
          const hash = raw.indexOf('#');
          const fragment = hash < 0 ? '' : decodeURIComponent(raw.slice(hash + 1));
          const targetPart = decodeURIComponent((hash < 0 ? raw : raw.slice(0, hash)).split('?')[0]);
          const target = targetPart ? resolve(dirname(path), targetPart) : path;
          if (!this.contains(target)) {
            this.error(path, `link escapes repository: ${raw}`);
            continue;
          }
          if (!existsSync(target)) {
            this.error(path, `missing link target: ${raw}`);
            continue;
          }
          if (!this.contains(realpathSync(target))) {
            this.error(path, `link resolves outside repository: ${raw}`);
            continue;
          }
          if (fragment && extname(target) === '.md' && !this.inspect(target, false).anchors.has(fragment)) {
            this.error(path, `missing heading/anchor: ${raw}`);
          }
        } catch {
          this.error(path, `invalid local link: ${raw}`);
        }
      }
    }
  }

  contains(path) {
    const location = relative(this.root, path);
    return location !== '..' && !location.startsWith(`..${sep}`) && resolve(this.root, location) === path;
  }

  run() {
    const docs = resolve(this.root, 'docs');
    if (lstatSync(docs).isSymbolicLink()) throw new Error('The docs root must not be a symlink');
    const files = [resolve(this.root, 'AGENTS.md'), ...markdownFiles(docs)];
    for (const path of files) this.inspect(path);
    for (const path of files) this.checkLinks(path, this.documents.get(path));
    if (this.errors.length) {
      process.stderr.write(`${this.errors.join('\n')}\n`);
      process.exitCode = 1;
    } else {
      process.stdout.write(`PASS: ${files.length} Markdown files; metadata, headings, and ${this.linkCount} local links checked.\n`);
    }
  }
}

try {
  new HandbookValidator(process.argv[2] ?? process.cwd()).run();
} catch (error) {
  process.stderr.write(`Documentation check failed: ${error.message}\n`);
  process.exitCode = 1;
}
