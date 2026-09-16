export const firstName = (name: string) => name.split(" ")[0];
export const shorten = (name: string, max = 20) => (name.length > max ? `${name.slice(0, max - 1).trimEnd()}…` : name);

/**
 * Category-axis tick that renders a shortened label and carries the full name
 * in an SVG <title>, so hovering the label shows it. Used with interval={0} so
 * Recharts renders every label instead of dropping the ones that would overlap.
 */
export function NameTick({ x, y, payload, textAnchor, format, dy }: any) {
  const full = String(payload?.value ?? "");
  return (
    <text x={x} y={y} dy={dy} textAnchor={textAnchor} fontSize={10} fill="var(--color-muted-foreground)" style={{ cursor: "default" }}>
      <title>{full}</title>
      {format(full)}
    </text>
  );
}
