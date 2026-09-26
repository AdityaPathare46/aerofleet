const METRES_PER_DEG_LAT = 111320

/** Flat-earth east/north metres from a reference point — accurate to well under
 * 0.1% across a city-sized area, and matches the backend's /cities/{slug}/roads. */
export function toLocal(lat: number, lon: number, center: [number, number]): [number, number] {
  const east = (lon - center[1]) * METRES_PER_DEG_LAT * Math.cos((center[0] * Math.PI) / 180)
  const north = (lat - center[0]) * METRES_PER_DEG_LAT
  return [east, north]
}

/**
 * Maps real-world metres onto a tabletop diorama (world-in-miniature).
 *
 *  - x = east, -z = north, so viewed from above the map is not mirrored.
 *  - Horizontal scale fits `extentM` (half-width, metres) into `tableHalf` metres.
 *  - Vertical is exaggerated so the 0-120 m legal airspace column reads at ~`columnHeight`
 *    above the table; the exaggeration factor is always shown to the viewer.
 */
export class Diorama {
  readonly scale: number
  readonly vExag: number

  constructor(
    readonly focusEast: number,
    readonly focusNorth: number,
    readonly extentM: number,
    readonly tableHalf = 0.7,
    readonly columnHeight = 0.32,
    readonly legalCeilingM = 120,
  ) {
    this.scale = tableHalf / extentM
    this.vExag = columnHeight / (legalCeilingM * this.scale)
  }

  x(east: number): number { return (east - this.focusEast) * this.scale }
  z(north: number): number { return -(north - this.focusNorth) * this.scale }
  y(altitudeM: number): number { return altitudeM * this.scale * this.vExag }

  point(east: number, north: number, altitudeM = 0): [number, number, number] {
    return [this.x(east), this.y(altitudeM), this.z(north)]
  }

  metres(worldUnits: number): number { return worldUnits / this.scale }

  contains(east: number, north: number, pad = 0): boolean {
    const h = this.extentM + pad
    return Math.abs(east - this.focusEast) <= h && Math.abs(north - this.focusNorth) <= h
  }
}

/** A "nice" round distance for a scale bar about a quarter of the table wide. */
export function niceScaleBar(extentM: number): number {
  const target = extentM / 2
  const pow = 10 ** Math.floor(Math.log10(target))
  for (const m of [5, 2, 1]) if (m * pow <= target) return m * pow
  return pow
}

export function fmtDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(m >= 10000 ? 0 : 1)} km` : `${Math.round(m)} m`
}
