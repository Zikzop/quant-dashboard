export default function ProbabilityPanel({
    market,
  }: any) {
  
    return (
  
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5">
  
        <h2 className="text-lg font-bold text-green-400 mb-4">
          Probabilities
        </h2>
  
        <div className="space-y-5">
  
          <ProbabilityBar
            label="Bull Probability"
            value={market.bull_probability}
            color="bg-green-500"
          />
  
          <ProbabilityBar
            label="Trend Probability"
            value={market.trend_probability}
            color="bg-cyan-500"
          />
  
          <ProbabilityBar
            label="Crisis Probability"
            value={market.crisis_probability}
            color="bg-red-500"
          />
  
        </div>
  
      </div>
    );
  }
  
  function ProbabilityBar({
    label,
    value,
    color,
  }: any) {
  
    return (
  
      <div>
  
        <div className="flex justify-between mb-2">
  
          <span className="text-zinc-400 text-sm">
            {label}
          </span>
  
          <span className="text-white font-bold">
            {value}%
          </span>
  
        </div>
  
        <div className="w-full h-3 bg-zinc-800 rounded-full overflow-hidden">
  
          <div
            className={`${color} h-full rounded-full`}
            style={{
              width: `${value}%`,
            }}
          />
  
        </div>
  
      </div>
    );
  }