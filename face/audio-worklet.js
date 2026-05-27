class MicProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const { targetRate, actualRate } = options.processorOptions || {};
    this._step = (actualRate && targetRate && actualRate !== targetRate)
      ? actualRate / targetRate
      : 1;
    this._pos = 0;
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel || channel.length === 0) return true;

    if (this._step === 1) {
      const pcm = new Int16Array(channel.length);
      for (let i = 0; i < channel.length; i++) {
        pcm[i] = Math.max(-32768, Math.min(32767, Math.round(channel[i] * 32767)));
      }
      this.port.postMessage(pcm.buffer, [pcm.buffer]);
    } else {
      // Decimate to targetRate (nearest-neighbor, adequate for speech)
      const out = [];
      while (this._pos < channel.length) {
        const idx = Math.floor(this._pos);
        out.push(Math.max(-32768, Math.min(32767, Math.round(channel[idx] * 32767))));
        this._pos += this._step;
      }
      this._pos -= channel.length;
      if (out.length > 0) {
        const pcm = new Int16Array(out);
        this.port.postMessage(pcm.buffer, [pcm.buffer]);
      }
    }
    return true;
  }
}

registerProcessor('mic-processor', MicProcessor);
