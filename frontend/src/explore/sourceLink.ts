/** The reference map's homepage is context, not a citation for one operation. */
export function isReferenceMapHome(url: string): boolean {
  try {
    const link = new URL(url);
    return (
      (link.protocol === "https:" || link.protocol === "http:") &&
      link.hostname === "map.sosmediterranee.org" &&
      link.pathname === "/" &&
      !link.search &&
      !link.hash &&
      !link.username &&
      !link.password
    );
  } catch {
    return false;
  }
}
