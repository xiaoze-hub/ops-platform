/**
 * Offline debounce: only mark a node offline after N consecutive backend misses.
 * Any successful online poll resets the miss counter.
 */
export class OfflineDebouncer {
  private misses = new Map<string, number>()
  private readonly threshold: number

  constructor(threshold = 2) {
    this.threshold = threshold
  }

  /** Returns the display-online flag after debounce. */
  update(nodeId: string, backendOnline: boolean): boolean {
    if (backendOnline) {
      this.misses.set(nodeId, 0)
      return true
    }
    const next = (this.misses.get(nodeId) || 0) + 1
    this.misses.set(nodeId, next)
    return next < this.threshold
  }

  reset(): void {
    this.misses.clear()
  }
}

export const offlineDebouncer = new OfflineDebouncer(2)
