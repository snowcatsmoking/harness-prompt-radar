// Minimal, purpose-built markdown renderer for system prompt text.
// Handles: #/##/### headers, -/* bullets (with indent-based nesting),
// fenced code blocks, inline `code` and **bold**. Everything else is a
// paragraph. Not a general-purpose parser — just enough for these four
// prompts' actual structure.

function renderInline(text) {
  const frag = document.createDocumentFragment();
  const pattern = /`([^`]+)`|\*\*([^*]+)\*\*/g;
  let last = 0, m;
  while ((m = pattern.exec(text)) !== null) {
    if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
    if (m[1] !== undefined) {
      const code = document.createElement('code');
      code.textContent = m[1];
      frag.appendChild(code);
    } else {
      const strong = document.createElement('strong');
      strong.textContent = m[2];
      frag.appendChild(strong);
    }
    last = pattern.lastIndex;
  }
  if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
  return frag;
}

function bulletIndent(line) {
  const m = /^(\s*)[-*]\s+/.exec(line);
  return m ? m[1].length : -1;
}

// Renders markdown-ish text into `container`. Returns an array of
// {id, level, text} for headers encountered, in order, for building a TOC.
function renderMarkdown(text, container) {
  const lines = text.split('\n');
  const headers = [];
  let i = 0;
  let headerCount = 0;

  function slugify(s) {
    headerCount++;
    return 'h' + headerCount + '-' + s.toLowerCase().replace(/[^a-z0-9一-龥]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40);
  }

  while (i < lines.length) {
    const line = lines[i];

    // fenced code block
    if (/^```/.test(line.trim())) {
      const startIndent = line.match(/^\s*/)[0];
      const codeLines = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i].trim())) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // skip closing fence
      const pre = document.createElement('pre');
      const code = document.createElement('code');
      code.textContent = codeLines.join('\n');
      pre.appendChild(code);
      container.appendChild(pre);
      continue;
    }

    // headers
    const headerMatch = /^(#{1,3})\s+(.*)$/.exec(line);
    if (headerMatch) {
      const level = headerMatch[1].length;
      const text = headerMatch[2].trim();
      const id = slugify(text);
      const h = document.createElement('h' + (level + 3 > 6 ? 6 : level + 3));
      h.id = id;
      h.className = 'prompt-heading prompt-heading-' + level;
      h.appendChild(renderInline(text));
      container.appendChild(h);
      headers.push({ id, level, text });
      i++;
      continue;
    }

    // bullet list (consume contiguous bullet lines, track indent nesting)
    if (bulletIndent(line) >= 0) {
      const listStack = []; // stack of {indent, ul}
      while (i < lines.length && (bulletIndent(lines[i]) >= 0 || (lines[i].trim() === '' && i + 1 < lines.length && bulletIndent(lines[i + 1]) >= 0))) {
        if (lines[i].trim() === '') { i++; continue; }
        const indent = bulletIndent(lines[i]);
        const content = lines[i].replace(/^\s*[-*]\s+/, '');

        while (listStack.length && indent < listStack[listStack.length - 1].indent) {
          listStack.pop();
        }
        if (!listStack.length || indent > listStack[listStack.length - 1].indent) {
          const ul = document.createElement('ul');
          if (listStack.length) {
            const lastLi = listStack[listStack.length - 1].ul.lastElementChild;
            (lastLi || listStack[listStack.length - 1].ul).appendChild(ul);
          } else {
            container.appendChild(ul);
          }
          listStack.push({ indent, ul });
        }
        const li = document.createElement('li');
        li.appendChild(renderInline(content));
        listStack[listStack.length - 1].ul.appendChild(li);
        i++;
      }
      continue;
    }

    // blank line
    if (line.trim() === '') { i++; continue; }

    // paragraph: consume contiguous non-blank, non-bullet, non-header lines
    const paraLines = [line];
    i++;
    while (i < lines.length && lines[i].trim() !== '' && bulletIndent(lines[i]) < 0 && !/^#{1,3}\s/.test(lines[i]) && !/^```/.test(lines[i].trim())) {
      paraLines.push(lines[i]);
      i++;
    }
    const p = document.createElement('p');
    p.appendChild(renderInline(paraLines.join('\n')));
    container.appendChild(p);
  }

  return headers;
}
