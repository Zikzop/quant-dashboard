export default function RiskPanel({
    market,
  }: any) {
  
    return (
  
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5">
  
        <h2 className="text-lg font-bold text-red-400 mb-4">
          Risk Metrics
        </h2>
  
        <div className="space-y-4">
  
          <RiskMetric
            label="VaR 95%"
            value={market.var_95}
          />
  
          <RiskMetric
            label="Expected Shortfall"
            value={market.expected_shortfall}
          />
  
          <RiskMetric
            label="Max Drawdown"
            value={market.max_drawdown}
          />
  
          <RiskMetric
            label="Risk Regime"
            value={market.risk_regime}
          />
  
        </div>
  
      </div>
    );
  }
  
  function RiskMetric({
    label,
    value,
  }: any) {
  
    return (
  
      <div className="flex justify-between items-center">
  
        <span className="text-zinc-500">
          {label}
        </span>
  
        <span className="text-white font-bold">
          {value}
        </span>
  
      </div>
    );
  }