// Minimal line-level diff (LCS-based), no dependencies.
function diffLines(oldText, newText) {
  const a = oldText.split("\n");
  const b = newText.split("\n");
  const n = a.length, m = b.length;

  // LCS length table
  const dp = Array.from({ length: n + 1 }, () => new Int32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }

  const ops = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      ops.push({ type: "same", text: a[i] });
      i++; j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      ops.push({ type: "del", text: a[i] });
      i++;
    } else {
      ops.push({ type: "add", text: b[j] });
      j++;
    }
  }
  while (i < n) { ops.push({ type: "del", text: a[i] }); i++; }
  while (j < m) { ops.push({ type: "add", text: b[j] }); j++; }
  return ops;
}

function renderDiff(oldText, newText) {
  const ops = diffLines(oldText, newText);
  const container = document.createElement("div");
  container.className = "diff-view";
  for (const op of ops) {
    const line = document.createElement("div");
    line.className = "diff-line diff-" + op.type;
    const marker = op.type === "add" ? "+ " : op.type === "del" ? "- " : "  ";
    line.textContent = marker + op.text;
    container.appendChild(line);
  }
  return container;
}
