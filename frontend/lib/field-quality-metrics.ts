import type { ProfilingResult } from "./types";

export type ObservedCompleteness = {
  percentage: number;
  rowCount: number;
  populatedCount: number;
  nullCount: number;
  scanId: string;
  measuredAt: string;
};

export function calculateObservedCompleteness(
  profile: ProfilingResult | null,
): ObservedCompleteness | null {
  if (!profile) {
    return null;
  }

  const rowCount = profile.row_count;
  const nullCount = profile.null_count;

  if (
    !Number.isSafeInteger(rowCount) ||
    !Number.isSafeInteger(nullCount) ||
    rowCount <= 0 ||
    nullCount < 0 ||
    nullCount > rowCount
  ) {
    return null;
  }

  const populatedCount = rowCount - nullCount;

  return {
    percentage: (populatedCount / rowCount) * 100,
    rowCount,
    populatedCount,
    nullCount,
    scanId: profile.scan_id,
    measuredAt: profile.created_at,
  };
}
