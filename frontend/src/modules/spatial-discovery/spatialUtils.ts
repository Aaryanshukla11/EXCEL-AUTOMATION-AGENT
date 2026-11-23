/**
 * Converts 1-indexed column index to Excel column letter (e.g. 1 -> A, 27 -> AA).
 */
export function colIndexToLetter(colIdx: number): string {
  if (colIdx < 1 || colIdx > 16384) {
    return `C${colIdx}`;
  }
  let result = "";
  let idx = colIdx;
  while (idx > 0) {
    idx -= 1;
    result = String.fromCharCode(65 + (idx % 26)) + result;
    idx = Math.floor(idx / 26);
  }
  return result;
}

/**
 * Converts 1-indexed (row, col) to canonical A1 notation (e.g. row 4, col 2 -> 'B4').
 */
export function toA1(row: number, col: number): string {
  return `${colIndexToLetter(col)}${row}`;
}

export interface BoundingBoxCoordinates {
  readonly start_row?: number;
  readonly start_col?: number;
  readonly end_row?: number;
  readonly end_col?: number;
  readonly min_row?: number;
  readonly min_col?: number;
  readonly max_row?: number;
  readonly max_col?: number;
}

/**
 * Normalizes any bounding box (M01 start/end or M03/M04 min/max) into consistent 1-indexed bounds.
 */
export function normalizeBoundingBox(box: BoundingBoxCoordinates): {
  start_row: number;
  start_col: number;
  end_row: number;
  end_col: number;
} {
  const start_row = box.start_row ?? box.min_row ?? 1;
  const start_col = box.start_col ?? box.min_col ?? 1;
  const end_row = box.end_row ?? box.max_row ?? start_row;
  const end_col = box.end_col ?? box.max_col ?? start_col;
  return { start_row, start_col, end_row, end_col };
}

/**
 * Formats bounding box to A1 range (e.g. 'B4:G25').
 */
export function boundingBoxToA1(box: BoundingBoxCoordinates): string {
  const norm = normalizeBoundingBox(box);
  const topLeft = toA1(norm.start_row, norm.start_col);
  const bottomRight = toA1(norm.end_row, norm.end_col);
  return topLeft === bottomRight ? topLeft : `${topLeft}:${bottomRight}`;
}
