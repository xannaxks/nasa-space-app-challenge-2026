// MTM100m grid definition — single source of truth for the whole frontend.
// Values mirror aligned/alignment_stats.json (Mars MTM clon77_5E, 100 m/px).
//
// Grid:
//   width  = 565 px
//   height = 594 px
//   res    = 100 m
//   top-left corner (MTM easting/northing, metres):
//     originX = -39528.90637077264
//     originY =  1108513.8212198   (top edge)
//   transform: x = originX + col * res ; y = originY - row * res

export const GRID = {
  width: 565,
  height: 594,
  resM: 100,
  originX: -39528.90637077264,
  originY: 1108513.8212198,
  crsName: 'MTM_clon77_5E',
};

export const GEOUNIT_LOOKUP = {
  1: 'Aeb',
  2: 'Hnpf',
  3: 'NHjf1',
  4: 'NHjf2',
  5: 'Njf',
  6: 'Nle',
  7: 'Nnp1',
  8: 'Nnp2',
  9: 'Nrb',
  10: 'Nue',
  11: 'ce',
  12: 'ci',
  13: 'cr',
  14: 'su',
};

// ---------------------------------------------------------------------------
// Pixel <-> MTM metre conversions (row, col are zero-based raster indices)
// ---------------------------------------------------------------------------

export function pixelToMtm(row, col) {
  return {
    // centre of the pixel in MTM metres
    x: GRID.originX + (col + 0.5) * GRID.resM,
    y: GRID.originY - (row + 0.5) * GRID.resM,
  };
}

export function mtmToPixel(x, y) {
  const col = Math.floor((x - GRID.originX) / GRID.resM);
  const row = Math.floor((GRID.originY - y) / GRID.resM);
  if (col < 0 || col >= GRID.width || row < 0 || row >= GRID.height) return null;
  return { row, col };
}

export function isValidPixel(row, col) {
  return (
    Number.isInteger(row) &&
    Number.isInteger(col) &&
    row >= 0 &&
    row < GRID.height &&
    col >= 0 &&
    col < GRID.width
  );
}
