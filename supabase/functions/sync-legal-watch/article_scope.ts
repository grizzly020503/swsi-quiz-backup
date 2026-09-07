export type LegalQuestionLike = {
  id?: unknown;
  law?: unknown;
  question?: unknown;
  exp_why?: unknown;
  exp_others?: unknown;
  exp_trap?: unknown;
  exp_raw?: unknown;
  extension?: unknown;
};

export function normalizeArticleNo(value: unknown): string | null {
  let text = String(value ?? "").normalize("NFKC").trim();
  text = text.replace(/\s+/g, "");
  text = text.replace(/^第/, "").replace(/^§/, "");
  text = text
    .replace(/條之/g, "-")
    .replace(/條-/g, "-")
    .replace(/條$/, "")
    .replace(/之/g, "-");
  if (!/^\d+(?:-\d+)*$/.test(text)) return null;
  return text
    .split("-")
    .map((part) => String(Number(part)))
    .join("-");
}

function addRange(out: Set<string>, startRaw: string, endRaw: string) {
  const start = Number(startRaw);
  const end = Number(endRaw);
  if (!Number.isInteger(start) || !Number.isInteger(end)) return;
  if (end < start || end - start > 100) return;
  for (let n = start; n <= end; n += 1) out.add(String(n));
}

export function extractArticleRefs(values: unknown[]): Set<string> {
  const text = values
    .map((value) => String(value ?? "").normalize("NFKC"))
    .join(" ");
  const out = new Set<string>();

  // Chinese sub-article form: 第1055條之1.
  for (const match of text.matchAll(/第\s*(\d+)\s*條\s*之\s*(\d+)/g)) {
    const normalized = normalizeArticleNo(`${match[1]}-${match[2]}`);
    if (normalized) out.add(normalized);
  }

  // Explicit ranges: 第1110至1113條 / 第1110～1113條.
  for (const match of text.matchAll(/第\s*(\d+)\s*(?:至|到|~|～|－|—)\s*(\d+)\s*條/g)) {
    addRange(out, match[1], match[2]);
  }

  // ASCII hyphen is ambiguous: "1110-1113" is a range while "1055-1"
  // is the MOJ sub-article notation. A right side larger than the left side
  // is treated as a bounded range; otherwise it is a sub-article.
  for (const match of text.matchAll(/第\s*(\d+)\s*-\s*(\d+)\s*條/g)) {
    const left = Number(match[1]);
    const right = Number(match[2]);
    if (Number.isInteger(left) && Number.isInteger(right) && right > left) {
      addRange(out, match[1], match[2]);
    } else {
      const normalized = normalizeArticleNo(`${match[1]}-${match[2]}`);
      if (normalized) out.add(normalized);
    }
  }

  // Plain article citations. This intentionally also records the parent article
  // in "第1055條之1", making a parent-article amendment conservative.
  for (const match of text.matchAll(/第\s*(\d+)\s*條/g)) {
    const normalized = normalizeArticleNo(match[1]);
    if (normalized) out.add(normalized);
  }

  // Section-sign notation used in notes and audit material.
  for (const match of text.matchAll(/§\s*(\d+(?:-\d+)*)/g)) {
    const normalized = normalizeArticleNo(match[1]);
    if (normalized) out.add(normalized);
  }

  return out;
}

export function questionArticleRefs(question: LegalQuestionLike): Set<string> {
  return extractArticleRefs([
    question.law,
    question.question,
    question.exp_why,
    question.exp_others,
    question.exp_trap,
    question.exp_raw,
    question.extension,
  ]);
}

export function questionTouchesChangedArticles(
  question: LegalQuestionLike,
  changedArticles: unknown[],
): boolean {
  const refs = questionArticleRefs(question);
  if (!refs.size) return false;
  for (const value of changedArticles) {
    const normalized = normalizeArticleNo(value);
    if (normalized && refs.has(normalized)) return true;
  }
  return false;
}
