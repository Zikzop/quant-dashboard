export default function StructurePanel({
    market,
  }: any) {
  
    return (
  
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5">
  
        <h2 className="text-xl font-bold text-green-400 mb-5">
          Structure Analytics
        </h2>
  
        <div className="space-y-5">
  
          <Metric
            label="Trend"
            value={market.trend}
          />
  
          <Metric
            label="Momentum"
            value={market.momentum}
          />
  
          <Metric
            label="Signal Score"
            value={market.signal_score}
          />
  
          <Metric
            label="Confidence"
            value={market.confidence}
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
