export class TransitionLedger {
  constructor(lineageRoot) {
    this.lineageRoot = lineageRoot;
    this.events = [];
  }

  append(event, payload = {}) {
    const row = Object.freeze({
      seq: this.events.length + 1,
      event,
      lineage_root: this.lineageRoot,
      ...payload
    });
    this.events.push(row);
    return row;
  }

  snapshot() {
    return Object.freeze([...this.events]);
  }
}
