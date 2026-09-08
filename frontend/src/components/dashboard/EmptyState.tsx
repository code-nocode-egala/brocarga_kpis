/**
 * Placeholder row for a table that came back with nothing.
 *
 * The tabs render their full chrome — headers, KPI cards, axes — whether or not
 * the API returned rows, so an empty table needs a body that explains itself
 * rather than a collapsed one that reads as a rendering bug.
 */
export function EmptyRows({
  show,
  colSpan,
  message,
}: {
  show: boolean;
  colSpan: number;
  message: string;
}) {
  if (!show) return null;
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-10 text-center text-sm text-muted-foreground">
        {message}
      </td>
    </tr>
  );
}
