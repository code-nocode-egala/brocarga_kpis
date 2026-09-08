/**
 * Download `rows` as a CSV, taking the column set from the first row.
 *
 * Constrained to `object` rather than `Record<string, unknown>` so the payload
 * interfaces in `api-types.ts` can be passed straight through — a declared
 * interface has no index signature, and widening them all just to satisfy this
 * one call site would be the tail wagging the dog.
 *
 * This exports what is on screen. The complete extract, including the columns
 * the dashboard never receives, is `/api/transactions/export/`.
 */
export function toCsv<T extends object>(rows: T[], filename: string) {
  if (rows.length === 0) return;
  const headers = Object.keys(rows[0]);
  const cell = (row: T, key: string) => (row as Record<string, unknown>)[key];
  const esc = (v: unknown) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = [
    headers.join(","),
    ...rows.map((r) => headers.map((h) => esc(cell(r, h))).join(",")),
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
