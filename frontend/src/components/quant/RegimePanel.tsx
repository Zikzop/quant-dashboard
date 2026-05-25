export default function RegimePanel({
    market,
  }: any) {
  
    return (
  
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5">
  
        <h2 className="text-lg font-bold text-cyan-400 mb-4">
          Regime State
        </h2>
  
        <div className="space-y-4">
  
          <div>
            <p className="text-zinc-500 text-sm">
              Market Regime
            </p>
  
            <p className="text-2xl font-bold text-white">
              {market.regime}
            </p>
          </div>
  
          <div>
            <p className="text-zinc-500 text-sm">
              HMM Regime
            </p>
  
            <p className="text-xl font-bold text-orange-400">
              {market.hmm_regime}
            </p>
          </div>
  
          <div>
            <p className="text-zinc-500 text-sm">
              Volatility Regime
            </p>
  
            <p className="text-xl font-bold text-red-400">
              {market.vol_regime}
            </p>
          </div>
  
        </div>
  
      </div>
    );
  }