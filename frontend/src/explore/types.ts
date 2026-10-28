/** Shared public and private feed projection for the Explore screen. */
export type Status = "to_review" | "blocked" | "linked";

export interface FeedItem {
  id: string;
  date: string | null;
  kind: string | null;
  people: number | null;
  port: string | null;
  position: { longitude: number; latitude: number } | null;
  title: string | null;
  status: Status | null;
  line: number | null;
  /** Where the record comes from, shown on the closed card: the source, or the export row. */
  origin: string;
}

