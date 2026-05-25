export default function TopBar({
    market,
  }: any) {
  
    return (
  
      <div className="border-b border-zinc-900 bg-zinc-950 px-6 py-4">
  
        <div className="flex flex-wrap items-center justify-between gap-6">
  
          <div>
  
            <h1 className="text-4xl font-bold text-green-400">
              Quant Terminal
            </h1>
  
            <p className="text-zinc-500 mt-1">
              Institutional Market Analytics
            </p>
  
          </div>
  
          <div className="flex gap-8">
  
            <TopMetric
              label="BTC"
              value={`$${market.price}`}
            />
  
            <TopMetric
              label="Trend"
              value={market.trend}
            />
  
            <TopMetric
              label="Volatility"
              value={`${market.volatility}%`}
            />
  
            <TopMetric
              label="Signal"
              value={market.signal}
            />
  
          </div>
  
        </div>
  
      </div>
    );
  }
  
  function TopMetric({
    label,
    value,
  }: any) {
  
    return (
  
      <div>
  
        <p className="text-zinc-500 text-sm">
          {label}
        </p>
  
        <p className="text-xl font-bold text-white">
          {value}
        </p>
  
      </div>
    );
  }