import { TokenText } from "./bits";
import type { Reference } from "../types";

/** Token-aware word diff (LCS). Citation tokens are treated as atomic
 *  words so a diff can never split one in half. */
type Op = { kind: "same" | "del" | "ins"; text: string };

function tokenize(s: string): string[] {
  return s.match(/\[\[cite[pt]:[^\]]+\]\]|\S+|\s+/g) ?? [];
}

export function wordDiff(a: string, b: string): Op[] {
  const A = tokenize(a).filter((t) => t.trim() !== "");
  const B = tokenize(b).filter((t) => t.trim() !== "");
  const n = A.length, m = B.length;
  // LCS via DP on word arrays (sections are a few thousand words max)
  const dp: Uint32Array[] = [];
  for (let i = 0; i <= n; i++) dp.push(new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const ops: Op[] = [];
  let i = 0, j = 0;
  const push = (kind: Op["kind"], text: string) => {
    const lastOp = ops[ops.length - 1];
    if (lastOp && lastOp.kind === kind) lastOp.text += " " + text;
    else ops.push({ kind, text });
  };
  while (i < n && j < m) {
    if (A[i] === B[j]) { push("same", A[i]); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { push("del", A[i]); i++; }
    else { push("ins", B[j]); j++; }
  }
  while (i < n) { push("del", A[i]); i++; }
  while (j < m) { push("ins", B[j]); j++; }
  return ops;
}

export function DiffView({ before, after, refs }: {
  before: string; after: string; refs: Map<string, Reference>;
}) {
  const ops = wordDiff(before, after);
  return (
    <div className="diff">
      {ops.map((op, idx) => {
        const inner = <TokenText text={op.text} refs={refs} />;
        if (op.kind === "del") return <del key={idx}>{inner}</del>;
        if (op.kind === "ins") return <ins key={idx}>{inner}</ins>;
        return <span key={idx}>{inner}</span>;
      }).flatMap((el, idx) => [el, <span key={`sp${idx}`}> </span>])}
    </div>
  );
}
