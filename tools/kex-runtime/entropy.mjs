import crypto from 'node:crypto';

export class EntropyTape {
  constructor(replay = []) {
    this.replay = [...replay];
    this.cursor = 0;
    this.recorded = [];
  }

  choose(maxExclusive, label) {
    if (!Number.isInteger(maxExclusive) || maxExclusive < 1) {
      throw new Error(`Invalid entropy range for ${label}`);
    }

    let value;
    let source;
    if (this.cursor < this.replay.length) {
      value = Number(this.replay[this.cursor++]);
      if (!Number.isInteger(value) || value < 0 || value >= maxExclusive) {
        throw new Error(`Replay entropy ${value} invalid for 0..${maxExclusive - 1}: ${label}`);
      }
      source = 'RECORDED_REPLAY';
    } else {
      value = crypto.randomInt(maxExclusive);
      source = 'OS_CSPRNG';
    }

    const observation = Object.freeze({ label, range: maxExclusive, value, source });
    this.recorded.push(observation);
    return observation;
  }

  snapshot() {
    return Object.freeze([...this.recorded]);
  }
}
