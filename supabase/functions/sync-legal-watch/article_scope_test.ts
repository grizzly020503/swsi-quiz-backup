import {
  extractArticleRefs,
  normalizeArticleNo,
  questionTouchesChangedArticles,
} from "./article_scope.ts";

function assert(condition: unknown, message: string) {
  if (!condition) throw new Error(message);
}

Deno.test("normalizes MOJ and Chinese article numbers", () => {
  assert(normalizeArticleNo(" 1055-1 ") === "1055-1", "MOJ sub-article normalization failed");
  assert(normalizeArticleNo("第1055條之1") === "1055-1", "Chinese sub-article normalization failed");
});

Deno.test("extracts explicit article citations and bounded ranges", () => {
  const refs = extractArticleRefs([
    "民法 第188條",
    "民法 第1055條之1",
    "民法 第1110-1113條",
  ]);
  for (const expected of ["188", "1055", "1055-1", "1110", "1111", "1112", "1113"]) {
    assert(refs.has(expected), `missing article ref ${expected}`);
  }
  assert(!refs.has("1223"), "invented unrelated article");
});

Deno.test("scopes a Civil Code amendment to matching questions only", () => {
  const inheritance = {
    id: "inheritance",
    law: "民法 第1223條（特留分）",
    question: "依民法關於特留分之規定，下列何者正確？",
  };
  const custody = {
    id: "custody",
    law: "民法 第1055條之1（子女最佳利益）",
    question: "法院審酌未成年子女最佳利益時應注意何者？",
  };
  const generic = {
    id: "generic",
    law: "民法親屬編",
    question: "非婚生子女之親權如何行使？",
  };

  assert(questionTouchesChangedArticles(inheritance, ["1223"]), "matching article was not selected");
  assert(!questionTouchesChangedArticles(custody, ["1223"]), "unrelated explicit article was selected");
  assert(!questionTouchesChangedArticles(generic, ["1223"]), "generic canonical reference should not be guessed");
});
