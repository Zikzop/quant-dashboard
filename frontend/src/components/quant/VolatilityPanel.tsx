export default function VolatilityPanel({
    market,
  }: any) {
  
    return (
  
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5">
  
        <h2 className="text-xl font-bold text-yellow-400 mb-5">
          Volatility Analytics
        </h2>
  
        <div className="space-y-5">
  
          <Metric
            label="Realized Volatility"
            value={`${market.volatility}%`}
          />
  
          <Metric
            label="GARCH Volatility"
            value={market.garch_vol}
          />
  
          <Metric
            label="Volatility Regime"
            value={market.vol_regime}
          />
  
          <Metric
            label="Volatility Slope"
            value={market.vol_slope}
          />
  
        </div>
  
      </div>
    );
  }
  
  function Metric({
    label,
    value,
  }: any) {
  
    return (
  
      <div className="flex justify-between">
  
        <span className="text-zinc-500">
          {label}
        </span>
  
        <span className="text-white font-bold">
          {value}
        </span>
  
      </div>
    );
  }