export default function MarketFeed() {

    const news = [
  
      {
        title:
          "BTC volatility expansion detected",
        impact: "HIGH",
      },
  
      {
        title:
          "Macro liquidity tightening risk",
        impact: "MEDIUM",
      },
  
      {
        title:
          "Trend persistence weakening",
        impact: "LOW",
      },
    ];
  
    return (
  
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5">
  
        <h2 className="text-xl font-bold text-cyan-400 mb-5">
          Market Intelligence Feed
        </h2>
  
        <div className="space-y-4">
  
          {news.map((item, index) => (
  
            <div
              key={index}
              className="border-b border-zinc-800 pb-4"
            >
  
              <p className="text-white font-medium">
                {item.title}
              </p>
  
              <p className="text-zinc-500 text-sm mt-1">
                Impact: {item.impact}
              </p>
  
            </div>
  
          ))}
  
        </div>
  
      </div>
    );
  }